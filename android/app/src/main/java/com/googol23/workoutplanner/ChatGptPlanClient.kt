package com.googol23.workoutplanner

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import android.util.Log
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import org.json.JSONArray
import org.json.JSONObject
import java.math.BigInteger
import java.net.InetAddress
import java.net.ServerSocket
import java.net.URL
import java.net.URLEncoder
import java.nio.charset.StandardCharsets
import java.security.KeyFactory
import java.security.KeyStore
import java.security.MessageDigest
import java.security.SecureRandom
import java.security.Signature
import java.security.spec.RSAPublicKeySpec
import java.time.Instant
import java.util.UUID
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import javax.net.ssl.HttpsURLConnection

data class ChatGptCredential(
    val clientId: String,
    val accessToken: String,
    val refreshToken: String,
    val email: String,
    val subject: String,
    val expiresAt: Long,
    val scopes: Set<String>,
)

/** Native public-client Sign in with ChatGPT flow and one-shot Responses API inference. */
object ChatGptPlanClient {
    private const val AUTHORIZATION_ENDPOINT = "https://auth.openai.com/api/accounts/authorize"
    private const val TOKEN_ENDPOINT = "https://auth.openai.com/api/accounts/oauth/token"
    private const val DISCOVERY_ENDPOINT = "https://auth.openai.com/.well-known/openid-configuration"
    private const val RESOURCE = "https://api.openai.com/v1"
    private const val ISSUER = "https://auth.openai.com"
    private const val CALLBACK_PATH = "/auth/callback"
    private const val STORE_PREFS = "chatgpt_plan_credentials"
    private const val TOKEN_PREF = "encrypted_session"
    private const val CLIENT_PREF = "issued_client_id"
    private const val HOST_PREF = "host_id"
    private const val KEY_ALIAS = "workoutplanner_chatgpt_plan_v1"
    private const val MAX_HTTP_BYTES = 8 * 1024 * 1024
    private const val LOG_TAG = "WorkoutPlannerAuth"

    fun hasCredentials(context: Context): Boolean = context.getSharedPreferences(STORE_PREFS, Context.MODE_PRIVATE).contains(TOKEN_PREF)

    fun email(context: Context): String? = runCatching { read(context).email }.getOrNull()

    fun disconnect(context: Context) {
        val prefs = context.getSharedPreferences(STORE_PREFS, Context.MODE_PRIVATE)
        check(prefs.edit().remove(TOKEN_PREF).remove(CLIENT_PREF).commit()) { "Could not remove the ChatGPT connection from this phone." }
        val ks = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        if (ks.containsAlias(KEY_ALIAS)) ks.deleteEntry(KEY_ALIAS)
    }

    suspend fun signIn(
        context: Context,
        onProgress: suspend (String) -> Unit = {},
    ): ChatGptCredential = withContext(Dispatchers.IO) {
        var stage = "initialize"
        Log.i(LOG_TAG, "Sign-in started")
        val preferences = context.getSharedPreferences(STORE_PREFS, Context.MODE_PRIVATE)
        val hostId = preferences.getString(HOST_PREF, null) ?: "urn:uuid:${UUID.randomUUID()}".also {
            check(preferences.edit().putString(HOST_PREF, it).commit()) { "Could not initialize this phone's ChatGPT connection." }
        }
        val existingClientId = preferences.getString(CLIENT_PREF, null)
            ?: runCatching { read(context).clientId }.getOrNull()
        val callback = try {
            ServerSocket(if (existingClientId == null) 1455 else 0, 1, InetAddress.getByName("127.0.0.1"))
        } catch (_: Exception) {
            throw IllegalStateException("Could not open the local ChatGPT sign-in callback port. Close another app using port 1455 and retry.")
        }
        callback.soTimeout = 180_000
        val redirectUri = "http://127.0.0.1:${callback.localPort}$CALLBACK_PATH"
        val state = randomUrlToken(32)
        val nonce = randomUrlToken(32)
        val verifier = randomUrlToken(48)
        val challenge = Base64.encodeToString(
            MessageDigest.getInstance("SHA-256").digest(verifier.toByteArray(StandardCharsets.US_ASCII)),
            Base64.URL_SAFE or Base64.NO_PADDING or Base64.NO_WRAP,
        )
        val result = CompletableDeferred<Map<String, String>>()
        val listener = Thread {
            try {
                callback.use { server ->
                    Log.i(LOG_TAG, "Loopback callback listener ready on port ${server.localPort}")
                    while (!result.isCompleted) {
                        val socket = server.accept()
                        socket.use { client ->
                            client.soTimeout = 10_000
                            val reader = client.getInputStream().bufferedReader(StandardCharsets.US_ASCII)
                            val requestLine = reader.readLine().orEmpty()
                            while (reader.readLine().orEmpty().isNotEmpty()) { /* drain headers */ }
                            val pieces = requestLine.split(' ')
                            val method = pieces.getOrNull(0).orEmpty()
                            val target = pieces.getOrNull(1).orEmpty()
                            val uri = Uri.parse("http://127.0.0.1$target")
                            val validCallback = method == "GET" && uri.path == CALLBACK_PATH
                            Log.i(LOG_TAG, "Loopback request received: method=$method path=${uri.path} matched=$validCallback")
                            val params = mutableMapOf<String, String>()
                            if (validCallback) uri.queryParameterNames.forEach { key -> params[key] = uri.getQueryParameter(key).orEmpty() }
                            val body = if (validCallback) {
                                "<html><body>WorkoutPlanner received the sign-in return. You can return to the app.</body></html>"
                            } else {
                                "<html><body>WorkoutPlanner sign-in is still waiting for ChatGPT authorization.</body></html>"
                            }
                            val bytes = body.toByteArray(StandardCharsets.UTF_8)
                            val status = if (validCallback) "200 OK" else "404 Not Found"
                            client.getOutputStream().write(("HTTP/1.1 $status\r\nContent-Type: text/html; charset=utf-8\r\nConnection: close\r\nContent-Length: ${bytes.size}\r\n\r\n").toByteArray(StandardCharsets.US_ASCII))
                            client.getOutputStream().write(bytes)
                            client.getOutputStream().flush()
                            if (validCallback) result.complete(params)
                        }
                    }
                }
            } catch (error: Exception) { result.completeExceptionally(error) }
        }.apply { name = "workoutplanner-chatgpt-oauth-callback"; isDaemon = true; start() }

        val issuedClientId = existingClientId
        val query = linkedMapOf(
            "client_id" to (issuedClientId ?: "dynamic_agent_client"),
            "response_type" to "code", "redirect_uri" to redirectUri,
            "scope" to "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct",
            "resource" to RESOURCE, "state" to state, "nonce" to nonce,
            "code_challenge_method" to "S256", "code_challenge" to challenge,
        )
        if (issuedClientId == null) {
            query["agent_name_hint"] = "WorkoutPlanner"
            query["ext_agent_host_id"] = hostId
        }
        val authUri = Uri.parse(AUTHORIZATION_ENDPOINT).buildUpon().apply {
            query.forEach { (key, value) -> appendQueryParameter(key, value) }
        }.build()
        try {
            stage = "browser authorization"
            Log.i(LOG_TAG, "Opening system browser for authorization; registration=${if (issuedClientId == null) "new" else "existing"}")
            withContext(Dispatchers.Main) { onProgress("Waiting for ChatGPT authorization in the browser…") }
            context.startActivity(Intent(Intent.ACTION_VIEW, authUri).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            val params = try {
                withTimeout(180_000) { result.await() }
            } catch (_: TimeoutCancellationException) {
                throw IllegalStateException("ChatGPT did not return to WorkoutPlanner. Keep the app open, finish authorization in the browser, then retry.")
            }
            Log.i(LOG_TAG, "Authorization callback received: code=${!params["code"].isNullOrBlank()} state=${!params["state"].isNullOrBlank()} clientId=${!params["client_id"].isNullOrBlank()} error=${!params["error"].isNullOrBlank()}")
            require(params["state"] == state) { "ChatGPT sign-in state did not match. Try again." }
            params["error"]?.let { code ->
                val message = if (code == "access_denied") "ChatGPT plan access was not authorized." else "ChatGPT sign-in failed ($code)."
                throw IllegalStateException(message)
            }
            val code = params["code"]?.takeIf(String::isNotBlank) ?: error("ChatGPT did not return an authorization code.")
            val clientId = params["client_id"]?.takeIf(String::isNotBlank) ?: issuedClientId
                ?: error("ChatGPT did not return its issued client ID. Registration was not completed.")
            if (issuedClientId != null && clientId != issuedClientId) error("ChatGPT returned a different client registration than expected.")
            check(preferences.edit().putString(CLIENT_PREF, clientId).commit()) {
                "Could not save the ChatGPT client registration for retry."
            }
            stage = "authorization code exchange"
            Log.i(LOG_TAG, "Exchanging authorization code")
            withContext(Dispatchers.Main) { onProgress("Authorization returned. Exchanging the one-time code…") }
            val token = exchangeToken(mapOf(
                "grant_type" to "authorization_code", "client_id" to clientId, "code" to code,
                "code_verifier" to verifier, "redirect_uri" to redirectUri, "resource" to RESOURCE,
            ))
            Log.i(LOG_TAG, "Authorization code exchange completed")
            val scopes = token.optString("scope").split(' ').filter(String::isNotBlank).toSet()
            Log.i(LOG_TAG, "Plan usage scopes granted: direct=${"chatgpt.tokens.use.direct" in scopes} invoke=${"resource.invoke" in scopes}")
            require("chatgpt.tokens.use.direct" in scopes && "resource.invoke" in scopes) {
                "ChatGPT sign-in succeeded, but plan usage was not authorized. Reconnect and approve plan usage."
            }
            val idToken = token.optString("id_token")
            stage = "identity verification"
            Log.i(LOG_TAG, "Verifying identity token")
            withContext(Dispatchers.Main) { onProgress("Verifying the ChatGPT account and granted permissions…") }
            val claims = verifyIdToken(idToken, clientId, nonce)
            Log.i(LOG_TAG, "Identity token verified")
            val subject = claims.getString("sub")
            val email = claims.optString("email")
            if (issuedClientId != null) {
                val previous = read(context)
                require(previous.subject == subject) { "The signed-in ChatGPT account differs from the saved account. Disconnect first to switch accounts." }
            }
            val credential = ChatGptCredential(
                clientId, token.getString("access_token"), token.optString("refresh_token"),
                email, subject, Instant.now().epochSecond + token.optLong("expires_in", 3600), scopes,
            )
            write(context, credential)
            stage = "credential storage"
            Log.i(LOG_TAG, "Encrypted credentials saved")
            withContext(Dispatchers.Main) { onProgress("ChatGPT connected.") }
            credential
        } catch (error: Exception) {
            Log.e(LOG_TAG, "Sign-in failed at stage=$stage (${error.javaClass.simpleName})")
            if (error is IllegalStateException) throw error
            throw IllegalStateException(error.message ?: "ChatGPT sign-in failed or timed out.")
        } finally {
            runCatching { callback.close() }
            listener.interrupt()
        }
    }

    suspend fun generate(context: Context, prompt: String): String = withContext(Dispatchers.IO) {
        require(prompt.isNotBlank()) { "Build the planning preview before generating." }
        val credential = currentCredential(context)
        require("chatgpt.tokens.use.direct" in credential.scopes && "resource.invoke" in credential.scopes) {
            "This ChatGPT connection does not include permission to use the ChatGPT plan. Reconnect and approve it."
        }
        val models = request("GET", "$RESOURCE/models", credential.accessToken).let(::JSONObject).optJSONArray("models")
            ?: throw IllegalStateException("ChatGPT did not return its available models.")
        val model = (0 until models.length()).asSequence().mapNotNull { models.optJSONObject(it) }
            .firstOrNull { it.optString("visibility") == "list" }?.optString("slug")
            ?.takeIf(String::isNotBlank) ?: throw IllegalStateException("No model is currently available for this ChatGPT account.")
        val body = JSONObject().put("model", model)
            .put("input", JSONArray().put(JSONObject().put("role", "user").put("content", prompt)))
            .put("store", false).put("stream", true)
        return@withContext streamResponse(credential.accessToken, body)
    }

    private fun currentCredential(context: Context): ChatGptCredential {
        var saved = read(context)
        if (saved.expiresAt > Instant.now().epochSecond + 90) return saved
        if (saved.refreshToken.isBlank()) throw IllegalStateException("ChatGPT sign-in expired. Reconnect your account.")
        val token = exchangeToken(mapOf(
            "grant_type" to "refresh_token", "client_id" to saved.clientId,
            "refresh_token" to saved.refreshToken, "resource" to RESOURCE,
        ))
        val scopes = token.optString("scope").takeIf(String::isNotBlank)?.split(' ')?.toSet() ?: saved.scopes
        saved = saved.copy(
            accessToken = token.getString("access_token"),
            refreshToken = token.optString("refresh_token").ifBlank { saved.refreshToken },
            expiresAt = Instant.now().epochSecond + token.optLong("expires_in", 3600), scopes = scopes,
        )
        write(context, saved)
        return saved
    }

    private fun streamResponse(accessToken: String, body: JSONObject): String {
        val connection = URL("$RESOURCE/responses").openConnection() as HttpsURLConnection
        try {
            connection.requestMethod = "POST"
            connection.connectTimeout = 20_000
            connection.readTimeout = 90_000
            connection.doOutput = true
            connection.setRequestProperty("Authorization", "Bearer $accessToken")
            connection.setRequestProperty("Content-Type", "application/json")
            connection.setRequestProperty("Accept", "text/event-stream")
            connection.outputStream.use { it.write(body.toString().toByteArray(StandardCharsets.UTF_8)) }
            if (connection.responseCode !in 200..299) throw apiError(connection.responseCode)
            val result = StringBuilder()
            var completed = false
            connection.inputStream.bufferedReader(StandardCharsets.UTF_8).useLines { lines ->
                lines.filter { it.startsWith("data:") }.forEach { line ->
                    val data = line.removePrefix("data:").trim()
                    if (data.isEmpty() || data == "[DONE]") return@forEach
                    val event = JSONObject(data)
                    when (event.optString("type")) {
                        "response.output_text.delta" -> result.append(event.optString("delta"))
                        "response.failed" -> throw IllegalStateException("ChatGPT could not generate a workout. Review your plan access and try again.")
                        "response.completed" -> completed = true
                    }
                    if (result.length > 500_000) throw IllegalStateException("ChatGPT's response exceeded the 500 KB safety limit.")
                }
            }
            if (!completed) throw IllegalStateException("ChatGPT's response stream ended before completion. Try again.")
            return result.toString().trim().takeIf(String::isNotEmpty) ?: throw IllegalStateException("ChatGPT returned an empty workout response.")
        } finally { connection.disconnect() }
    }

    private fun exchangeToken(values: Map<String, String>): JSONObject = postForm(TOKEN_ENDPOINT, values)

    private fun postForm(url: String, values: Map<String, String>): JSONObject {
        val body = values.entries.joinToString("&") { "${enc(it.key)}=${enc(it.value)}" }.toByteArray(StandardCharsets.UTF_8)
        val connection = URL(url).openConnection() as HttpsURLConnection
        try {
            connection.requestMethod = "POST"
            connection.connectTimeout = 20_000
            connection.readTimeout = 30_000
            connection.doOutput = true
            connection.setRequestProperty("Content-Type", "application/x-www-form-urlencoded")
            connection.outputStream.use { it.write(body) }
            val status = connection.responseCode
            val source = if (status in 200..299) connection.inputStream else connection.errorStream
            val text = source?.use { readLimited(it, 256 * 1024) }.orEmpty()
            if (status !in 200..299) throw apiError(status, text)
            return JSONObject(text)
        } finally { connection.disconnect() }
    }

    private fun request(method: String, url: String, token: String?): String {
        val connection = URL(url).openConnection() as HttpsURLConnection
        try {
            connection.requestMethod = method
            connection.connectTimeout = 20_000
            connection.readTimeout = 30_000
            if (!token.isNullOrBlank()) connection.setRequestProperty("Authorization", "Bearer $token")
            val status = connection.responseCode
            val source = if (status in 200..299) connection.inputStream else connection.errorStream
            val text = source?.use { readLimited(it, MAX_HTTP_BYTES) }.orEmpty()
            if (status !in 200..299) throw apiError(status, text)
            return text
        } finally { connection.disconnect() }
    }

    private fun verifyIdToken(jwt: String, clientId: String, expectedNonce: String): JSONObject {
        val parts = jwt.split('.')
        require(parts.size == 3) { "ChatGPT returned an invalid identity token." }
        val header = JSONObject(String(decodeUrl(parts[0]), StandardCharsets.UTF_8))
        val claims = JSONObject(String(decodeUrl(parts[1]), StandardCharsets.UTF_8))
        require(header.optString("alg") == "RS256") { "ChatGPT used an unsupported identity-token signature." }
        val configuration = JSONObject(request("GET", DISCOVERY_ENDPOINT, ""))
        require(configuration.optString("issuer") == ISSUER) { "ChatGPT identity issuer was unexpected." }
        val jwksUri = Uri.parse(configuration.getString("jwks_uri"))
        require(jwksUri.scheme == "https" && jwksUri.host == "auth.openai.com") { "ChatGPT identity keys came from an unexpected host." }
        val keys = JSONObject(request("GET", jwksUri.toString(), "")).optJSONArray("keys") ?: error("ChatGPT identity keys were unavailable.")
        val kid = header.optString("kid")
        val jwk = (0 until keys.length()).asSequence().mapNotNull { keys.optJSONObject(it) }.firstOrNull { it.optString("kid") == kid }
            ?: error("ChatGPT identity signing key was not found.")
        require(jwk.optString("kty") == "RSA" && (jwk.optString("use").isBlank() || jwk.optString("use") == "sig")) { "ChatGPT identity key type was unexpected." }
        val modulus = BigInteger(1, decodeUrl(jwk.getString("n")))
        val exponent = BigInteger(1, decodeUrl(jwk.getString("e")))
        val publicKey = KeyFactory.getInstance("RSA").generatePublic(RSAPublicKeySpec(modulus, exponent))
        val signature = Signature.getInstance("SHA256withRSA")
        signature.initVerify(publicKey)
        signature.update("${parts[0]}.${parts[1]}".toByteArray(StandardCharsets.US_ASCII))
        require(signature.verify(decodeUrl(parts[2]))) { "ChatGPT identity-token signature was invalid." }
        val audience = claims.opt("aud")
        val audienceMatches = audience == clientId || (audience is JSONArray && (0 until audience.length()).any { audience.optString(it) == clientId })
        require(audienceMatches && claims.optString("iss") == ISSUER) { "ChatGPT identity token was for a different app or issuer." }
        if (audience is JSONArray && audience.length() > 1) require(claims.optString("azp") == clientId) {
            "ChatGPT identity token authorized a different client."
        }
        require(claims.optString("nonce") == expectedNonce) { "ChatGPT identity token did not match this sign-in attempt." }
        require(claims.optLong("exp") > Instant.now().epochSecond) { "ChatGPT identity token has expired." }
        require(claims.optString("sub").isNotBlank()) { "ChatGPT did not return a verified account ID." }
        return claims
    }

    private fun apiError(status: Int, body: String = ""): IllegalStateException = when (status) {
        401 -> IllegalStateException("ChatGPT connection expired. Reconnect your account and try again.")
        403 -> IllegalStateException("ChatGPT plan usage is not enabled for this app or account. No API-billing fallback was attempted.")
        429 -> IllegalStateException("ChatGPT plan usage limit reached. Try again later or check your ChatGPT plan controls.")
        else -> IllegalStateException("ChatGPT request failed (HTTP $status). ${if (body.isNotBlank()) "Check account eligibility and network access." else "Try again later."}")
    }

    private fun read(context: Context): ChatGptCredential {
        val encrypted = context.getSharedPreferences(STORE_PREFS, Context.MODE_PRIVATE).getString(TOKEN_PREF, null)
            ?: throw IllegalStateException("Connect ChatGPT before generating a workout.")
        return try {
            val envelope = Base64.decode(encrypted, Base64.NO_WRAP)
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(Cipher.DECRYPT_MODE, encryptionKey(), GCMParameterSpec(128, envelope.copyOfRange(0, 12)))
            val json = JSONObject(String(cipher.doFinal(envelope.copyOfRange(12, envelope.size)), StandardCharsets.UTF_8))
            ChatGptCredential(json.getString("client_id"), json.getString("access_token"), json.getString("refresh_token"),
                json.getString("email"), json.getString("subject"), json.getLong("expires_at"),
                json.getJSONArray("scopes").let { a -> (0 until a.length()).map(a::getString).toSet() })
        } catch (_: Exception) { throw IllegalStateException("Saved ChatGPT credentials cannot be decrypted. Disconnect and reconnect.") }
    }

    private fun write(context: Context, credential: ChatGptCredential) {
        val json = JSONObject().put("client_id", credential.clientId).put("access_token", credential.accessToken)
            .put("refresh_token", credential.refreshToken).put("email", credential.email)
            .put("subject", credential.subject).put("expires_at", credential.expiresAt).put("scopes", JSONArray(credential.scopes))
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, encryptionKey())
        val payload = cipher.iv + cipher.doFinal(json.toString().toByteArray(StandardCharsets.UTF_8))
        check(context.getSharedPreferences(STORE_PREFS, Context.MODE_PRIVATE).edit()
            .putString(TOKEN_PREF, Base64.encodeToString(payload, Base64.NO_WRAP)).commit()) { "Could not save the encrypted ChatGPT connection." }
    }

    private fun encryptionKey(): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getKey(KEY_ALIAS, null) as? SecretKey)?.let { return it }
        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        generator.init(KeyGenParameterSpec.Builder(KEY_ALIAS, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .setKeySize(256).setRandomizedEncryptionRequired(true).build())
        return generator.generateKey()
    }

    private fun randomUrlToken(bytes: Int): String = Base64.encodeToString(ByteArray(bytes).also(SecureRandom()::nextBytes), Base64.URL_SAFE or Base64.NO_PADDING or Base64.NO_WRAP)
    private fun enc(value: String): String = URLEncoder.encode(value, "UTF-8")
    private fun decodeUrl(value: String): ByteArray = Base64.decode(value, Base64.URL_SAFE or Base64.NO_PADDING or Base64.NO_WRAP)
    private fun readLimited(input: java.io.InputStream, limit: Int): String {
        val out = java.io.ByteArrayOutputStream()
        val buffer = ByteArray(8192)
        var total = 0
        while (true) { val n = input.read(buffer); if (n < 0) break; total += n; require(total <= limit) { "ChatGPT response exceeded the size limit." }; out.write(buffer, 0, n) }
        return out.toString("UTF-8")
    }
}
