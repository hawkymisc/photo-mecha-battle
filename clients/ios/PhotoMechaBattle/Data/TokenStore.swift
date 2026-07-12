import Foundation
import Security

/// docs/11 共通アーキテクチャ: X-User-Token の永続化（Keychain）。
final class TokenStore: @unchecked Sendable {

    private let service = "com.photomecha.battle"

    var token: String? {
        get { read(key: "user_token") }
        set { write(key: "user_token", value: newValue) }
    }

    var pilotName: String? {
        get { read(key: "pilot_name") }
        set { write(key: "pilot_name", value: newValue) }
    }

    /// 401 時の再登録導線（docs/11 エラー時遷移）。
    func clear() {
        token = nil
        pilotName = nil
    }

    private func read(key: String) -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)
        guard status == errSecSuccess, let data = result as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    private func write(key: String, value: String?) {
        let base: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key,
        ]
        SecItemDelete(base as CFDictionary)
        guard let value else { return }
        var attributes = base
        attributes[kSecValueData as String] = Data(value.utf8)
        attributes[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        let status = SecItemAdd(attributes as CFDictionary, nil)
        if status != errSecSuccess {
            // Keychain 書込失敗はセッション維持不能として表面化させる（error-surfacing）
            NSLog("[TokenStore] SecItemAdd failed for %@: %d", key, status)
        }
    }
}
