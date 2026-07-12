package com.photomecha.battle

import android.app.Application
import com.photomecha.battle.data.CaptureFlowState
import com.photomecha.battle.data.TokenStore
import com.photomecha.core.api.ApiClient

class PmbApplication : Application() {

    lateinit var tokenStore: TokenStore
        private set
    lateinit var apiClient: ApiClient
        private set

    /** 撮影 → 選択 → 分析の画面間で受け渡す作業状態（docs/11 S02〜S04）。 */
    val captureFlow = CaptureFlowState()

    override fun onCreate() {
        super.onCreate()
        tokenStore = TokenStore(this)
        apiClient = ApiClient(
            baseUrl = BuildConfig.PMB_API_BASE_URL,
            tokenProvider = { tokenStore.token },
        )
    }
}
