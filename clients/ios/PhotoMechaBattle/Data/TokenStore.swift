import Foundation
import Security

/// Keychain 書込失敗（トークンが永続化できずセッションが再起動で切れる状態）。
struct KeychainWriteError: Error {
    let key: String
    let status: OSStatus
}

/// docs/11 共通アーキテクチャ: X-User-Token の永続化（Keychain）。
final class TokenStore: @unchecked Sendable {

    private let service = "com.photomecha.battle"

    var token: String? { read(key: "user_token") }
    var pilotName: String? { read(key: "pilot_name") }

    /// 登録成功時の保存。Keychain 書込失敗は握り潰さず throw する（error-surfacing）。
    func save(token: String, pilotName: String) throws {
        try write(key: "user_token", value: token)
        try write(key: "pilot_name", value: pilotName)
    }

    /// 401 時の再登録導線（docs/11 エラー時遷移）。
    func clear() {
        delete(key: "user_token")
        delete(key: "pilot_name")
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

    private func write(key: String, value: String) throws {
        delete(key: key)
        var attributes: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key,
            kSecValueData as String: Data(value.utf8),
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly,
        ]
        let status = SecItemAdd(attributes as CFDictionary, nil)
        if status != errSecSuccess {
            NSLog("[TokenStore] SecItemAdd failed for %@: %d", key, status)
            throw KeychainWriteError(key: key, status: status)
        }
    }

    private func delete(key: String) {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key,
        ]
        SecItemDelete(query as CFDictionary)
    }
}
