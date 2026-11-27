package com.googol23.workoutplanner

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/** Encrypts the user-entered Garmin Personal API key with an Android Keystore key. */
class GarminSecretStore(context: Context) {
    private val preferences = context.getSharedPreferences("garmin_credentials", Context.MODE_PRIVATE)
    private val keyAlias = "workoutplanner_garmin_personal_key_v1"

    fun hasKey(): Boolean = preferences.contains(KEY_PREF)

    fun save(apiKey: String) {
        require(apiKey.isNotBlank() && apiKey.isAsciiToken()) { "Enter a valid Garmin Personal API key." }
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.ENCRYPT_MODE, encryptionKey())
        val ciphertext = cipher.doFinal(apiKey.toByteArray(Charsets.UTF_8))
        val envelope = cipher.iv + ciphertext
        check(preferences.edit().putString(KEY_PREF, Base64.encodeToString(envelope, Base64.NO_WRAP)).commit()) {
            "Could not save the encrypted Garmin key on this phone."
        }
    }

    fun read(): String {
        val stored = preferences.getString(KEY_PREF, null)
            ?: throw IllegalStateException("Save your Garmin Personal API key first.")
        return try {
            val envelope = Base64.decode(stored, Base64.NO_WRAP)
            require(envelope.size > IV_BYTES) { "Invalid encrypted key data." }
            val iv = envelope.copyOfRange(0, IV_BYTES)
            val ciphertext = envelope.copyOfRange(IV_BYTES, envelope.size)
            val cipher = Cipher.getInstance(TRANSFORMATION)
            cipher.init(Cipher.DECRYPT_MODE, encryptionKey(), GCMParameterSpec(TAG_BITS, iv))
            String(cipher.doFinal(ciphertext), Charsets.UTF_8)
        } catch (error: Exception) {
            throw IllegalStateException("The saved Garmin key cannot be decrypted. Remove it and save the key again.")
        }
    }

    fun clear() {
        check(preferences.edit().remove(KEY_PREF).commit()) { "Could not remove the saved Garmin key." }
        val keyStore = KeyStore.getInstance(ANDROID_KEYSTORE).apply { load(null) }
        if (keyStore.containsAlias(keyAlias)) keyStore.deleteEntry(keyAlias)
    }

    private fun encryptionKey(): SecretKey {
        val keyStore = KeyStore.getInstance(ANDROID_KEYSTORE).apply { load(null) }
        (keyStore.getKey(keyAlias, null) as? SecretKey)?.let { return it }
        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, ANDROID_KEYSTORE)
        generator.init(
            KeyGenParameterSpec.Builder(
                keyAlias,
                KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT,
            )
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256)
                .setRandomizedEncryptionRequired(true)
                .build(),
        )
        return generator.generateKey()
    }

    private fun String.isAsciiToken(): Boolean =
        all { it.code in 0x21..0x7e } && none(Char::isWhitespace)

    private companion object {
        const val KEY_PREF = "encrypted_garmin_personal_key"
        const val ANDROID_KEYSTORE = "AndroidKeyStore"
        const val TRANSFORMATION = "AES/GCM/NoPadding"
        const val IV_BYTES = 12
        const val TAG_BITS = 128
    }
}
