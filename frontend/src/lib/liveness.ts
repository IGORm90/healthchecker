// Liveness backend: ok — API и БД живы, error — API жив, БД нет, unavailable — API не ответил.
export type Liveness = 'ok' | 'error' | 'unavailable';
