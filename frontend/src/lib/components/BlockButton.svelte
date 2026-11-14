<script lang="ts">
	import { enhance } from '$app/forms';
	import type { UserSummary } from '#lib/auth.ts';

	// Отправляет в действие `block` или `unblock` текущей страницы.
	let { user }: { user: Pick<UserSummary, 'id' | 'name' | 'blocked_at'> } = $props();

	let blocked = $derived(user.blocked_at !== null);
	let busy = $state(false);
</script>

<form
	method="POST"
	action={blocked ? '?/unblock' : '?/block'}
	use:enhance={({ cancel }) => {
		// confirm() — в enhance: preventDefault() в onsubmit enhance не останавливает.
		const question = `Заблокировать пользователя «${user.name}»? Он выйдет из сервиса, а его мониторы перестанут проверяться.`;
		if (!blocked && !confirm(question)) return cancel();
		busy = true;
		return async ({ update }) => {
			await update();
			busy = false;
		};
	}}
>
	<input type="hidden" name="user_id" value={user.id} />
	<button
		class={blocked ? 'btn-secondary' : 'btn-danger'}
		disabled={busy}
		aria-label="{blocked ? 'Разблокировать' : 'Заблокировать'} пользователя «{user.name}»"
		>{blocked ? 'Разблокировать' : 'Заблокировать'}</button
	>
</form>
