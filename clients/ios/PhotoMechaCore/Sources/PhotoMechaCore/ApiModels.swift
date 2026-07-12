import Foundation

public struct RegisterRequest: Codable, Sendable {
    public let name: String

    public init(name: String) {
        self.name = name
    }
}

public struct RegisterResponse: Codable, Sendable {
    public let userId: String
    public let name: String
    public let token: String
    public let rating: Int

    enum CodingKeys: String, CodingKey {
        case userId = "user_id"
        case name, token, rating
    }
}

public struct QuotaEntry: Codable, Sendable {
    public let used: Int
    public let limit: Int
    public let remaining: Int
}

public struct QuotasResponse: Codable, Sendable {
    public let captures: QuotaEntry
    public let mechs: QuotaEntry
}

public struct MechDirectPayload: Codable, Sendable {
    public let name: String
    public let algoVersion: String
    public let bbox: [Double]?
    public let features: [String: Double]

    public init(name: String, algoVersion: String, bbox: [Double]?, features: [String: Double]) {
        self.name = name
        self.algoVersion = algoVersion
        self.bbox = bbox
        self.features = features
    }

    enum CodingKeys: String, CodingKey {
        case name
        case algoVersion = "algo_version"
        case bbox, features
    }
}

public struct MechResponse: Codable, Sendable {
    public let id: String
    public let objectId: String?
    public let name: String
    public let form: String
    public let stats: [String: Int]
    public let artUrl: String?
    public let features: [String: Double]?
    public let infoScore: Double?

    enum CodingKeys: String, CodingKey {
        case id, name, form, stats, features
        case objectId = "object_id"
        case artUrl = "art_url"
        case infoScore = "info_score"
    }
}

public struct MechListResponse: Codable, Sendable {
    public let mechs: [MechSummary]
}

public struct MechSummary: Codable, Sendable, Identifiable, Equatable {
    public let id: String
    public let name: String
    public let form: String
    public let stats: [String: Int]
    public let artUrl: String?

    enum CodingKeys: String, CodingKey {
        case id, name, form, stats
        case artUrl = "art_url"
    }
}

public struct TacticPreset: Codable, Sendable, Identifiable, Equatable {
    public let id: String
    public let name: String
    public let label: String
}

public struct TacticPresetsResponse: Codable, Sendable {
    public let presets: [TacticPreset]
}

public struct BattleSlotRequest: Codable, Sendable {
    public let mechId: String
    public let position: String
    public let preset: String

    public init(mechId: String, position: String, preset: String) {
        self.mechId = mechId
        self.position = position
        self.preset = preset
    }

    enum CodingKeys: String, CodingKey {
        case mechId = "mech_id"
        case position, preset
    }
}

public struct BattleCreateRequest: Codable, Sendable {
    public let teamName: String
    public let slots: [BattleSlotRequest]
    public let seed: Int

    public init(teamName: String, slots: [BattleSlotRequest], seed: Int) {
        self.teamName = teamName
        self.slots = slots
        self.seed = seed
    }

    enum CodingKeys: String, CodingKey {
        case teamName = "team_name"
        case slots, seed
    }
}

public struct BattleCreateResponse: Codable, Sendable {
    public let id: String
    public let seed: Int64
    public let winnerTeamId: String?
    public let turns: Int
    public let log: String

    enum CodingKeys: String, CodingKey {
        case id, seed, turns, log
        case winnerTeamId = "winner_team_id"
    }
}

public struct DamageEvent: Codable, Sendable, Equatable {
    public let targetId: String
    public let targetName: String
    public let damage: Int
    public let defeated: Bool

    enum CodingKeys: String, CodingKey {
        case damage, defeated
        case targetId = "target_id"
        case targetName = "target_name"
    }
}

public struct BattleLogEntry: Codable, Sendable, Equatable {
    public let turn: Int
    public let actorTeam: String
    public let actorPosition: String
    public let actorName: String
    public let conditionLabel: String
    public let action: String
    public let damageEvents: [DamageEvent]
    public let note: String

    enum CodingKeys: String, CodingKey {
        case turn, action
        case actorTeam = "actor_team"
        case actorPosition = "actor_position"
        case actorName = "actor_name"
        case conditionLabel = "condition_label"
        case damageEvents = "damage_events"
        case note
    }

    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        turn = try container.decode(Int.self, forKey: .turn)
        actorTeam = try container.decode(String.self, forKey: .actorTeam)
        actorPosition = try container.decode(String.self, forKey: .actorPosition)
        actorName = try container.decode(String.self, forKey: .actorName)
        conditionLabel = try container.decode(String.self, forKey: .conditionLabel)
        action = try container.decode(String.self, forKey: .action)
        damageEvents = try container.decodeIfPresent([DamageEvent].self, forKey: .damageEvents) ?? []
        note = try container.decodeIfPresent(String.self, forKey: .note) ?? ""
    }
}

public struct BattleDetailResponse: Codable, Sendable {
    public let id: String
    public let seed: Int64
    public let winnerTeamId: String?
    public let turns: Int
    public let log: String
    public let logEntries: [BattleLogEntry]

    enum CodingKeys: String, CodingKey {
        case id, seed, turns, log
        case winnerTeamId = "winner_team_id"
        case logEntries = "log_entries"
    }

    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decode(String.self, forKey: .id)
        seed = try container.decode(Int64.self, forKey: .seed)
        winnerTeamId = try container.decodeIfPresent(String.self, forKey: .winnerTeamId)
        turns = try container.decode(Int.self, forKey: .turns)
        log = try container.decode(String.self, forKey: .log)
        logEntries = try container.decodeIfPresent([BattleLogEntry].self, forKey: .logEntries) ?? []
    }
}
