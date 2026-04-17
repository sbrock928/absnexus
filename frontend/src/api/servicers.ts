import { api } from "./client";
import type { Servicer } from "../types";

export function fetchServicers(): Promise<Servicer[]> {
  return api.get<Servicer[]>("/servicers/");
}

export function createServicer(body: {
  name: string;
  short_code: string;
}): Promise<Servicer> {
  return api.post<Servicer>("/servicers/", body);
}
