package com.photomecha.battle.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.photomecha.battle.PmbApplication
import com.photomecha.core.api.ApiErrorKind
import com.photomecha.core.api.ApiException
import com.photomecha.core.api.BattleCreateRequest
import com.photomecha.core.api.BattleSlotRequest
import com.photomecha.core.api.MechSummary
import com.photomecha.core.api.TacticPreset
import kotlinx.coroutines.launch
import kotlin.random.Random

private val POSITIONS = listOf("front", "middle", "back")

/**
 * S06 出撃編成（docs/11）。前衛・中衛・後衛にメカとプリセット戦術を割り当て、
 * CPU デモ戦（POST /battles）を開始する。
 */
@Composable
fun FormationScreen(
    app: PmbApplication,
    onBattleStarted: (String) -> Unit,
    onUnauthorized: () -> Unit,
) {
    var mechs by remember { mutableStateOf<List<MechSummary>?>(null) }
    var presets by remember { mutableStateOf<List<TacticPreset>?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    val selectedMech = remember { mutableStateMapOf<String, MechSummary>() }
    val selectedPreset = remember { mutableStateMapOf<String, TacticPreset>() }
    var busy by remember { mutableStateOf(false) }
    var reloadKey by remember { mutableStateOf(0) }
    val scope = rememberCoroutineScope()

    LaunchedEffect(reloadKey) {
        error = null
        try {
            mechs = app.apiClient.listMechs().mechs
            presets = app.apiClient.tacticPresets().presets
        } catch (e: ApiException) {
            if (e.kind == ApiErrorKind.UNAUTHORIZED) onUnauthorized() else error = e.userMessage()
        }
    }

    when {
        error != null -> ErrorBox(error!!) { reloadKey++ }
        mechs == null || presets == null -> LoadingBox("編成データを取得中…")
        else -> Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
        ) {
            Text("出撃編成", style = MaterialTheme.typography.headlineSmall)
            Text(
                "3 つの位置にメカと戦術プリセットを割り当ててください",
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(bottom = 8.dp),
            )
            for (position in POSITIONS) {
                SlotCard(
                    position = position,
                    mechs = mechs!!.filter { candidate ->
                        selectedMech.filterKeys { it != position }.values.none { it.id == candidate.id }
                    },
                    presets = presets!!,
                    selectedMech = selectedMech[position],
                    selectedPreset = selectedPreset[position],
                    onMechSelected = { selectedMech[position] = it },
                    onPresetSelected = { selectedPreset[position] = it },
                )
            }
            val ready = POSITIONS.all { selectedMech[it] != null && selectedPreset[it] != null }
            Button(
                onClick = {
                    busy = true
                    scope.launch {
                        try {
                            val request = BattleCreateRequest(
                                teamName = app.tokenStore.pilotName ?: "Player",
                                slots = POSITIONS.map { position ->
                                    BattleSlotRequest(
                                        mechId = selectedMech.getValue(position).id,
                                        position = position,
                                        preset = selectedPreset.getValue(position).id,
                                    )
                                },
                                // CPU デモ戦のみクライアント seed 可（ランク戦はサーバー生成、docs/09）
                                seed = Random.nextInt(0, Int.MAX_VALUE),
                            )
                            val battle = app.apiClient.createDemoBattle(request)
                            onBattleStarted(battle.id)
                        } catch (e: ApiException) {
                            if (e.kind == ApiErrorKind.UNAUTHORIZED) onUnauthorized() else error = e.userMessage()
                        } finally {
                            busy = false
                        }
                    }
                },
                enabled = ready && !busy,
                modifier = Modifier.fillMaxWidth().padding(top = 16.dp),
            ) {
                Text(if (busy) "出撃中…" else "CPU 戦に出撃")
            }
        }
    }
}

@Composable
private fun SlotCard(
    position: String,
    mechs: List<MechSummary>,
    presets: List<TacticPreset>,
    selectedMech: MechSummary?,
    selectedPreset: TacticPreset?,
    onMechSelected: (MechSummary) -> Unit,
    onPresetSelected: (TacticPreset) -> Unit,
) {
    Card(modifier = Modifier.fillMaxWidth().padding(vertical = 6.dp)) {
        Column(modifier = Modifier.padding(12.dp)) {
            Text(positionLabel(position), style = MaterialTheme.typography.titleMedium)
            SelectorDropdown(
                label = selectedMech?.let { "${it.name}（${formLabel(it.form)}）" } ?: "メカを選択",
                options = mechs.map { "${it.name}（${formLabel(it.form)}）" },
                onSelected = { index -> onMechSelected(mechs[index]) },
            )
            SelectorDropdown(
                label = selectedPreset?.label ?: "戦術プリセットを選択",
                options = presets.map { it.label },
                onSelected = { index -> onPresetSelected(presets[index]) },
            )
        }
    }
}

@Composable
private fun SelectorDropdown(label: String, options: List<String>, onSelected: (Int) -> Unit) {
    var expanded by remember { mutableStateOf(false) }
    OutlinedButton(
        onClick = { expanded = true },
        modifier = Modifier.fillMaxWidth().padding(top = 4.dp),
    ) {
        Text(label)
    }
    DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
        options.forEachIndexed { index, option ->
            DropdownMenuItem(
                text = { Text(option) },
                onClick = {
                    onSelected(index)
                    expanded = false
                },
            )
        }
    }
}
