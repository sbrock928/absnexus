import { api } from "./client";
import type { User } from "../types";

export function fetchUsers(): Promise<User[]> {
  return api.get<User[]>("/users/");
}

export function createUser(body: {
  username: string;
  display_name: string;
  role: string;
}): Promise<User> {
  return api.post<User>("/auth/users", body);
}

export function updateUser(
  userId: number,
  body: { role?: string; is_active?: boolean },
): Promise<User> {
  return api.patch<User>(`/users/${userId}`, body);
}
