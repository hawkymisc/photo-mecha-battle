package com.photomecha.battle.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.photomecha.battle.PmbApplication
import com.photomecha.core.api.ApiException
import kotlinx.coroutines.launch

/** S00 パイロット登録（docs/11）。 */
@Composable
fun RegisterScreen(app: PmbApplication, onRegistered: () -> Unit) {
    var name by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    Column(
        modifier = Modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.Center,
    ) {
        Text("Photo Mecha Battle", style = MaterialTheme.typography.headlineMedium)
        Text(
            "パイロット名を入力して出撃準備",
            style = MaterialTheme.typography.bodyMedium,
            modifier = Modifier.padding(top = 8.dp, bottom = 24.dp),
        )
        OutlinedTextField(
            value = name,
            onValueChange = { name = it },
            label = { Text("パイロット名") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        error?.let {
            Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(top = 8.dp))
        }
        Button(
            onClick = {
                busy = true
                error = null
                scope.launch {
                    try {
                        val response = app.apiClient.register(name.trim())
                        app.tokenStore.token = response.token
                        app.tokenStore.pilotName = response.name
                        onRegistered()
                    } catch (e: ApiException) {
                        error = e.userMessage()
                    } finally {
                        busy = false
                    }
                }
            },
            enabled = name.isNotBlank() && !busy,
            modifier = Modifier.fillMaxWidth().padding(top = 16.dp),
        ) {
            Text(if (busy) "登録中…" else "登録して始める")
        }
    }
}
