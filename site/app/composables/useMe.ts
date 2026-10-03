// The one who came in (Discord), or null. Until the API: a mock account.
export interface Me { nick: string; hue: number; unread: number; role: "user" | "mod" | "owner" }

export const useMe = () => useState<Me | null>("me", () => ({ nick: "frostmonk", hue: 200, unread: 3, role: "owner" }));
