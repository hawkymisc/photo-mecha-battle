package com.photomecha.battle.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import com.photomecha.battle.PmbApplication
import com.photomecha.core.api.ApiErrorKind
import com.photomecha.core.api.ApiException
import com.photomecha.core.api.MechSummary
import com.photomecha.core.api.QuotasResponse

/** S01 ホーム / ハンガー（docs/11）。 */
@Composable
fun HomeScreen(
    app: PmbApplication,
    onCapture: () -> Unit,
    onMechSelected: (String) -> Unit,
    onFormation: () -> Unit,
    onUnauthorized: () -> Unit,
) {
    var mechs by remember { mutableStateOf<List<MechSummary>?>(null) }
    var quotas by remember { mutableStateOf<QuotasResponse?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var reloadKey by remember { mutableIntStateOf(0) }

    LaunchedEffect(reloadKey) {
        error = null
        try {
            mechs = app.apiClient.listMechs().mechs
            quotas = app.apiClient.quotas()
        } catch (e: ApiException) {
            if (e.kind == ApiErrorKind.UNAUTHORIZED) onUnauthorized() else error = e.userMessage()
        }
    }

    when {
        error != null -> ErrorBox(error!!) { reloadKey++ }
        mechs == null -> LoadingBox("ハンガーを読み込み中…")
        else -> Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
            Text(
                "ハンガー（${app.tokenStore.pilotName ?: "パイロット"}）",
                style = MaterialTheme.typography.headlineSmall,
            )
            quotas?.let {
                Text(
                    "本日の残り生成枠: 撮影 ${it.captures.remaining} / メカ ${it.mechs.remaining}",
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.padding(vertical = 4.dp),
                )
            }
            LazyColumn(modifier = Modifier.weight(1f)) {
                items(mechs!!) { mech ->
                    Card(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(vertical = 4.dp)
                            .clickable { onMechSelected(mech.id) },
                    ) {
                        Row(
                            modifier = Modifier.padding(12.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            AsyncImage(
                                model = app.apiClient.mediaUrl(mech.artUrl),
                                contentDescription = mech.name,
                                modifier = Modifier.size(56.dp),
                            )
                            Column(modifier = Modifier.padding(start = 12.dp)) {
                                Text(mech.name, style = MaterialTheme.typography.titleMedium)
                                Text(
                                    "${formLabel(mech.form)}  HP ${mech.stats["hp"]}  ATK ${mech.stats["atk"]}",
                                    style = MaterialTheme.typography.bodySmall,
                                )
                            }
                        }
                    }
                }
            }
            if (mechs!!.size < 3) {
                Text(
                    "出撃にはメカが 3 体必要です（あと ${3 - mechs!!.size} 体）",
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.padding(vertical = 4.dp),
                )
            }
            Row(
                modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Button(onClick = onCapture, modifier = Modifier.weight(1f)) {
                    Text("撮影する")
                }
                OutlinedButton(
                    onClick = onFormation,
                    enabled = mechs!!.size >= 3,
                    modifier = Modifier.weight(1f),
                ) {
                    Text("出撃編成")
                }
            }
        }
    }
}
