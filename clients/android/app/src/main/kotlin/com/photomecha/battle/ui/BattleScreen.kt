package com.photomecha.battle.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
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
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.photomecha.battle.PmbApplication
import com.photomecha.core.api.ApiErrorKind
import com.photomecha.core.api.ApiException
import com.photomecha.core.api.BattleDetailResponse
import com.photomecha.core.api.BattleLogEntry
import kotlinx.coroutines.delay

/**
 * S07 バトル再生 / S08 結果・ログ（docs/11）。
 * サーバーの `log_entries` をターン順に演出再生する。勝敗・ダメージの再計算はしない
 * （docs/09 信頼モデル / AGENTS.md 不変条件 1）。
 */
@Composable
fun BattleScreen(
    app: PmbApplication,
    battleId: String,
    onRematch: () -> Unit,
    onHome: () -> Unit,
    onUnauthorized: () -> Unit,
) {
    var battle by remember { mutableStateOf<BattleDetailResponse?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var revealedCount by remember { mutableIntStateOf(0) }

    LaunchedEffect(battleId) {
        try {
            battle = app.apiClient.battleDetail(battleId)
        } catch (e: ApiException) {
            if (e.kind == ApiErrorKind.UNAUTHORIZED) onUnauthorized() else error = e.userMessage()
        }
    }

    // 演出再生: 0.8 秒ごとに 1 エントリずつ表示
    LaunchedEffect(battle) {
        val entries = battle?.logEntries ?: return@LaunchedEffect
        revealedCount = 0
        for (i in 1..entries.size) {
            delay(800)
            revealedCount = i
        }
    }

    when {
        error != null -> ErrorBox(error!!, retryLabel = "ホームへ") { onHome() }
        battle == null -> LoadingBox("バトル結果を取得中…")
        else -> {
            val data = battle!!
            val finished = revealedCount >= data.logEntries.size
            val listState = rememberLazyListState()

            LaunchedEffect(revealedCount) {
                if (revealedCount > 0) listState.animateScrollToItem(revealedCount - 1)
            }

            Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
                Text(
                    if (finished) {
                        if (data.winnerTeamId == "player") "勝利！" else if (data.winnerTeamId == null) "引き分け" else "敗北…"
                    } else {
                        "バトル進行中…（${data.turns} ターン）"
                    },
                    style = MaterialTheme.typography.headlineSmall,
                )
                LazyColumn(state = listState, modifier = Modifier.weight(1f).padding(vertical = 8.dp)) {
                    items(data.logEntries.take(revealedCount)) { entry ->
                        LogEntryCard(entry)
                    }
                }
                if (finished) {
                    Row(modifier = Modifier.fillMaxWidth()) {
                        OutlinedButton(onClick = onHome, modifier = Modifier.weight(1f)) {
                            Text("ホームへ")
                        }
                        Button(onClick = onRematch, modifier = Modifier.weight(1f).padding(start = 8.dp)) {
                            Text("再戦する")
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun LogEntryCard(entry: BattleLogEntry) {
    Card(modifier = Modifier.fillMaxWidth().padding(vertical = 3.dp)) {
        Column(modifier = Modifier.padding(10.dp)) {
            Text(
                "Turn ${entry.turn}  ${positionLabel(entry.actorPosition)} ${entry.actorName}",
                style = MaterialTheme.typography.titleSmall,
            )
            // docs/11 S08: 条件成立理由の表示（戦術改善につなげる）
            Text("条件「${entry.conditionLabel}」が成立 → ${entry.action}", style = MaterialTheme.typography.bodySmall)
            for (event in entry.damageEvents) {
                Text(
                    "→ ${event.targetName} に ${event.damage} ダメージ${if (event.defeated) "（撃破）" else ""}",
                    style = MaterialTheme.typography.bodySmall,
                )
            }
            if (entry.note.isNotEmpty()) {
                Text(entry.note, style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}
