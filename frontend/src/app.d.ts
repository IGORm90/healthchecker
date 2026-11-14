// See https://svelte.dev/docs/kit/types#app.d.ts
// for information about these interfaces
import type { User } from '#lib/auth.ts';

declare global {
	namespace App {
		// interface Error {}
		interface Locals {
			// null — вход не выполнен или Сессия недействительна.
			user: User | null;
			sessionToken: string | null;
		}
		// interface PageData {}
		// interface PageState {}
		// interface Platform {}
	}
}

export {};
