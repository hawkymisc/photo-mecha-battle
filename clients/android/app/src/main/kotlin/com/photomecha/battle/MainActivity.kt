package com.photomecha.battle

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.photomecha.battle.ui.AnalyzeScreen
import com.photomecha.battle.ui.BattleScreen
import com.photomecha.battle.ui.CaptureScreen
import com.photomecha.battle.ui.FormationScreen
import com.photomecha.battle.ui.HomeScreen
import com.photomecha.battle.ui.MechDetailScreen
import com.photomecha.battle.ui.RegisterScreen
import com.photomecha.battle.ui.SelectObjectScreen

/** docs/11 画面遷移。単一スタック・タブなし。 */
object Routes {
    const val REGISTER = "register"
    const val HOME = "home"
    const val CAPTURE = "capture"
    const val SELECT = "select"
    const val ANALYZE = "analyze"
    const val MECH_DETAIL = "mech/{mechId}"
    const val FORMATION = "formation"
    const val BATTLE = "battle/{battleId}"

    fun mechDetail(mechId: String) = "mech/$mechId"
    fun battle(battleId: String) = "battle/$battleId"
}

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val app = application as PmbApplication
        setContent {
            MaterialTheme {
                Surface {
                    PmbNavHost(app)
                }
            }
        }
    }
}

@Composable
fun PmbNavHost(app: PmbApplication, navController: NavHostController = rememberNavController()) {
    val start = if (app.tokenStore.token == null) Routes.REGISTER else Routes.HOME

    // docs/11 エラー時遷移: 401 はトークン破棄 → S00 へ
    val onUnauthorized: () -> Unit = {
        app.tokenStore.clear()
        navController.navigate(Routes.REGISTER) { popUpTo(0) }
    }

    NavHost(navController = navController, startDestination = start) {
        composable(Routes.REGISTER) {
            RegisterScreen(app) {
                navController.navigate(Routes.HOME) { popUpTo(0) }
            }
        }
        composable(Routes.HOME) {
            HomeScreen(
                app = app,
                onCapture = {
                    app.captureFlow.reset()
                    navController.navigate(Routes.CAPTURE)
                },
                onMechSelected = { navController.navigate(Routes.mechDetail(it)) },
                onFormation = { navController.navigate(Routes.FORMATION) },
                onUnauthorized = onUnauthorized,
            )
        }
        composable(Routes.CAPTURE) {
            CaptureScreen(app) { navController.navigate(Routes.SELECT) }
        }
        composable(Routes.SELECT) {
            SelectObjectScreen(
                app = app,
                onConfirmed = { navController.navigate(Routes.ANALYZE) },
                onRetake = { navController.popBackStack(Routes.CAPTURE, inclusive = false) },
            )
        }
        composable(Routes.ANALYZE) {
            AnalyzeScreen(
                app = app,
                onCreated = { mechId ->
                    navController.navigate(Routes.mechDetail(mechId)) {
                        popUpTo(Routes.HOME)
                    }
                },
                onRecapture = { navController.popBackStack(Routes.CAPTURE, inclusive = false) },
                onReselect = { navController.popBackStack(Routes.SELECT, inclusive = false) },
                onUnauthorized = onUnauthorized,
            )
        }
        composable(Routes.MECH_DETAIL) { entry ->
            MechDetailScreen(
                app = app,
                mechId = entry.arguments?.getString("mechId").orEmpty(),
                onBack = { navController.popBackStack(Routes.HOME, inclusive = false) },
            )
        }
        composable(Routes.FORMATION) {
            FormationScreen(
                app = app,
                onBattleStarted = { battleId ->
                    navController.navigate(Routes.battle(battleId))
                },
                onUnauthorized = onUnauthorized,
            )
        }
        composable(Routes.BATTLE) { entry ->
            BattleScreen(
                app = app,
                battleId = entry.arguments?.getString("battleId").orEmpty(),
                onRematch = { navController.popBackStack(Routes.FORMATION, inclusive = false) },
                onHome = { navController.popBackStack(Routes.HOME, inclusive = false) },
            )
        }
    }
}
