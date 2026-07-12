package com.photomecha.battle.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import com.photomecha.battle.PmbApplication
import com.photomecha.core.api.ApiErrorKind
import com.photomecha.core.api.ApiException
import com.photomecha.core.api.MechResponse

/** S05 メカ詳細（docs/11）。サーバー確定の型・ステータス・アートを表示する。 */
@Composable
fun MechDetailScreen(
    app: PmbApplication,
    mechId: String,
    onBack: () -> Unit,
    onUnauthorized: () -> Unit,
) {
    var mech by remember { mutableStateOf<MechResponse?>(null) }
    var error by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(mechId) {
        try {
            mech = app.apiClient.mechDetail(mechId)
        } catch (e: ApiException) {
            if (e.kind == ApiErrorKind.UNAUTHORIZED) onUnauthorized() else error = e.userMessage()
        }
    }

    when {
        error != null -> ErrorBox(error!!, retryLabel = "ホームへ") { onBack() }
        mech == null -> LoadingBox("メカ情報を取得中…")
        else -> {
            val data = mech!!
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .verticalScroll(rememberScrollState())
                    .padding(16.dp),
            ) {
                Text(data.name, style = MaterialTheme.typography.headlineSmall)
                Text(formLabel(data.form), style = MaterialTheme.typography.titleMedium)
                AsyncImage(
                    model = app.apiClient.mediaUrl(data.artUrl),
                    contentDescription = data.name,
                    modifier = Modifier.fillMaxWidth().height(240.dp).padding(vertical = 8.dp),
                )
                data.infoScore?.let {
                    Text("情報量スコア: ${"%.2f".format(it)}", style = MaterialTheme.typography.bodyMedium)
                }
                Text("ステータス", style = MaterialTheme.typography.titleSmall, modifier = Modifier.padding(top = 8.dp))
                for ((stat, value) in data.stats) {
                    Text("${stat.uppercase()}: $value", style = MaterialTheme.typography.bodyMedium)
                }
                Button(onClick = onBack, modifier = Modifier.fillMaxWidth().padding(top = 16.dp)) {
                    Text("ハンガーへ戻る")
                }
            }
        }
    }
}
