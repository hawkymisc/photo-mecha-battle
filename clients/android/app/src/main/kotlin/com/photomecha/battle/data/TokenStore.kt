package com.photomecha.battle.data

import android.content.Context
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

/** docs/11 共通アーキテクチャ: X-User-Token の永続化（EncryptedSharedPreferences）。 */
class TokenStore(context: Context) {

    private val prefs = EncryptedSharedPreferences.create(
        context,
        "pmb_secure_prefs",
        MasterKey.Builder(context).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build(),
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
    )

    var token: String?
        get() = prefs.getString(KEY_TOKEN, null)
        set(value) {
            prefs.edit().apply {
                if (value == null) remove(KEY_TOKEN) else putString(KEY_TOKEN, value)
            }.apply()
        }

    var pilotName: String?
        get() = prefs.getString(KEY_NAME, null)
        set(value) {
            prefs.edit().apply {
                if (value == null) remove(KEY_NAME) else putString(KEY_NAME, value)
            }.apply()
        }

    /** 401 時の再登録導線（docs/11 エラー時遷移）。 */
    fun clear() {
        prefs.edit().clear().apply()
    }

    private companion object {
        const val KEY_TOKEN = "user_token"
        const val KEY_NAME = "pilot_name"
    }
}
