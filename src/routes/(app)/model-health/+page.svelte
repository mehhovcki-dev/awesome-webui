<script lang="ts">
	import { getContext, onMount } from 'svelte';

	import { getPublicModelHealth } from '$lib/apis/model-health';
	import { WEBUI_API_BASE_URL } from '$lib/constants';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import ChevronUp from '$lib/components/icons/ChevronUp.svelte';
	import ChevronDown from '$lib/components/icons/ChevronDown.svelte';

	const i18n: any = getContext('i18n');

	type DailyBucket = {
		date: string;
		status: 'healthy' | 'degraded' | 'outage' | 'unknown';
		uptime_ratio?: number | null;
		successful_checks: number;
		total_checks: number;
	};

	type LatestStatus = {
		checked_at: number;
		status: boolean;
		latency_ms?: number | null;
		error?: string | null;
	};

	type ModelHealthItem = {
		id: string;
		name: string;
		provider?: string | null;
		latest?: LatestStatus | null;
		uptime_ratio_90d?: number | null;
		successful_checks_90d: number;
		total_checks_90d: number;
		history: DailyBucket[];
	};

	type ModelHealthResponse = {
		generated_at: number;
		last_run_at?: number | null;
		check_interval_seconds: number;
		history_window_days: number;
		models: ModelHealthItem[];
	};

	let loading = true;
	let error = '';
	let health: ModelHealthResponse | null = null;
	let query = '';
	let sortBy: 'name' | 'status' | 'uptime' | 'latency' = 'status';
	let direction: 'asc' | 'desc' = 'desc';
	const sortOptions = [
		{ value: 'status', label: 'Status' },
		{ value: 'name', label: 'Model' },
		{ value: 'uptime', label: 'Uptime' },
		{ value: 'latency', label: 'Latency' }
	] as const;

	const getErrorMessage = (value: unknown) => {
		if (typeof value === 'string') {
			return value;
		}

		if (value && typeof value === 'object' && 'detail' in value) {
			return String((value as { detail?: unknown }).detail ?? 'Failed to load model health');
		}

		return 'Failed to load model health';
	};

	const loadHealth = async () => {
		loading = true;
		error = '';

		try {
			health = await getPublicModelHealth();
		} catch (err) {
			error = getErrorMessage(err);
		} finally {
			loading = false;
		}
	};

	onMount(loadHealth);

	const normalizeChatDirection = (value?: string): 'ltr' | 'rtl' | 'auto' => {
		const normalized = String(value ?? 'auto').toLowerCase();
		return normalized === 'ltr' || normalized === 'rtl' ? normalized : 'auto';
	};

	const latestLabel = (item: ModelHealthItem) => {
		if (!item.latest) {
			return $i18n.t('Pending');
		}

		return item.latest.status ? $i18n.t('Operational') : $i18n.t('Major Outage');
	};

	const latestColorClass = (item: ModelHealthItem) => {
		if (!item.latest) {
			return 'text-gray-500 dark:text-gray-400';
		}

		return item.latest.status
			? 'text-emerald-500 dark:text-emerald-400'
			: 'text-red-500 dark:text-red-400';
	};

	const bucketClassName = (bucket: DailyBucket) => {
		if (bucket.status === 'healthy') {
			return 'bg-emerald-500';
		}
		if (bucket.status === 'degraded') {
			return 'bg-amber-400';
		}
		if (bucket.status === 'outage') {
			return 'bg-red-500';
		}
		return 'bg-gray-200 dark:bg-gray-800';
	};

	const formatDateTime = (timestamp?: number | null) => {
		if (!timestamp) {
			return $i18n.t('Not checked yet');
		}

		return new Intl.DateTimeFormat(undefined, {
			dateStyle: 'medium',
			timeStyle: 'short'
		}).format(new Date(timestamp * 1000));
	};

	const formatPercent = (ratio?: number | null) => {
		if (ratio === null || ratio === undefined) {
			return $i18n.t('No data yet');
		}

		return `${(ratio * 100).toFixed(2)}%`;
	};

	const formatInterval = (seconds: number) => {
		const hours = Math.max(1, Math.round(seconds / 3600));
		return hours === 1 ? $i18n.t('Every hour') : $i18n.t('Every {{HOURS}} hours', { HOURS: hours });
	};

	const bucketTooltip = (bucket: DailyBucket) => {
		const percent =
			bucket.uptime_ratio === null || bucket.uptime_ratio === undefined
				? $i18n.t('No checks')
				: `${(bucket.uptime_ratio * 100).toFixed(0)}% uptime`;

		return `${bucket.date} • ${percent} • ${bucket.successful_checks}/${bucket.total_checks}`;
	};

	$: totalModels = health?.models.length ?? 0;
	$: healthyModels = health?.models.filter((item) => item.latest?.status).length ?? 0;
	$: unhealthyModels =
		health?.models.filter((item) => item.latest && !item.latest.status).length ?? 0;
	$: normalizedQuery = query.trim().toLowerCase();

	const toggleSort = (key: 'name' | 'status' | 'uptime' | 'latency') => {
		if (sortBy === key) {
			direction = direction === 'asc' ? 'desc' : 'asc';
		} else {
			sortBy = key;
			direction = key === 'name' ? 'asc' : 'desc';
		}
	};

	const compareValues = (left: number | string, right: number | string) => {
		if (typeof left === 'string' && typeof right === 'string') {
			return left.localeCompare(right);
		}

		return Number(left) - Number(right);
	};

	$: visibleModels = (health?.models ?? [])
		.filter((item) => {
			if (!normalizedQuery) {
				return true;
			}

			const haystack = [item.name, item.provider ?? '', latestLabel(item)].join(' ').toLowerCase();
			return haystack.includes(normalizedQuery);
		})
		.sort((a, b) => {
			let left: number | string = '';
			let right: number | string = '';

			if (sortBy === 'name') {
				left = a.name;
				right = b.name;
			} else if (sortBy === 'status') {
				left = a.latest?.status ? 1 : 0;
				right = b.latest?.status ? 1 : 0;
			} else if (sortBy === 'uptime') {
				left = a.uptime_ratio_90d ?? -1;
				right = b.uptime_ratio_90d ?? -1;
			} else if (sortBy === 'latency') {
				left = a.latest?.latency_ms ?? -1;
				right = b.latest?.latency_ms ?? -1;
			}

			const result = compareValues(left, right);
			return direction === 'asc' ? result : -result;
		});
</script>

<svelte:head>
	<title>{$i18n.t('Model Health')}</title>
</svelte:head>

<div class="text-gray-900 dark:text-gray-100">
	<div class="mx-auto w-full max-w-full py-2">
		<div class="pb-1 gap-2 flex flex-col md:flex-row md:justify-between md:items-center">
			<div class="flex flex-wrap items-center gap-3 text-xs text-gray-500 dark:text-gray-400">
				<span>{formatInterval(health?.check_interval_seconds ?? 3600)}</span>
				<span>{$i18n.t('Last run')}: {formatDateTime(health?.last_run_at)}</span>
			</div>
		</div>

		{#if !loading}
			<div class="flex flex-wrap gap-3 text-xs text-gray-500 dark:text-gray-400 px-0.5 pb-3">
				<span
					><span class="font-medium text-gray-900 dark:text-gray-300">{totalModels}</span>
					{$i18n.t('models')}</span
				>
				<span
					><span class="font-medium text-gray-900 dark:text-gray-300">{healthyModels}</span>
					{$i18n.t('healthy')}</span
				>
				<span
					><span class="font-medium text-gray-900 dark:text-gray-300">{unhealthyModels}</span>
					{$i18n.t('failing')}</span
				>
			</div>
		{/if}

		<div class="flex flex-col gap-3 px-0.5 pb-3 md:flex-row md:items-center md:justify-between">
			<input
				bind:value={query}
				placeholder={$i18n.t('Search models')}
				class="w-full md:max-w-sm rounded-lg border border-gray-100 bg-transparent px-3 py-2 text-sm outline-hidden dark:border-gray-800"
			/>
			<div class="flex flex-wrap items-center gap-2">
				<select
					bind:value={sortBy}
					class="w-fit rounded-lg border border-gray-100 bg-transparent px-3 py-2 text-sm outline-hidden dark:border-gray-800"
				>
					{#each sortOptions as option}
						<option value={option.value}>{$i18n.t(option.label)}</option>
					{/each}
				</select>
				<button
					type="button"
					class="rounded-lg border border-gray-100 px-3 py-2 text-sm transition hover:bg-gray-50 dark:border-gray-800 dark:hover:bg-gray-850"
					on:click={() => {
						direction = direction === 'asc' ? 'desc' : 'asc';
					}}
				>
					{direction === 'asc' ? $i18n.t('Ascending') : $i18n.t('Descending')}
				</button>
				{#if !loading}
					<div class="text-xs text-gray-500 dark:text-gray-400">
						{visibleModels.length}
						{$i18n.t('shown')}
					</div>
				{/if}
			</div>
		</div>

		<div class="relative min-h-[160px]">
			{#if loading}
				<div
					class="absolute inset-0 flex items-center justify-center z-10 bg-white/50 dark:bg-gray-900/50"
				>
					<Spinner className="size-5" />
				</div>
			{/if}

			{#if error && !loading}
				<div class="text-center text-xs text-red-500 py-8">{error}</div>
			{:else if health && visibleModels.length > 0}
				<div class="space-y-3 md:hidden">
					{#each visibleModels as item (item.id)}
						<div class="rounded-xl border border-gray-100 p-3 dark:border-gray-800">
							<div class="flex items-start justify-between gap-3">
								<div class="min-w-0 flex items-start gap-2.5">
									<img
										src={`${WEBUI_API_BASE_URL}/models/model/profile/image?id=${item.id}`}
										alt={item.name}
										class="mt-0.5 size-8 rounded-full object-cover shrink-0"
										on:error={(e) => {
											(e.currentTarget as HTMLImageElement).src = '/favicon.png';
										}}
									/>
									<div class="min-w-0">
										<div class="font-medium text-sm text-gray-800 dark:text-gray-200 truncate">
											{item.name}
										</div>
										<div
											class="mt-1 text-[11px] text-gray-500 dark:text-gray-400 whitespace-nowrap"
										>
											{item.provider ?? $i18n.t('Model')}
										</div>
									</div>
								</div>
								<div class="text-right">
									<div class="font-medium text-xs whitespace-nowrap {latestColorClass(item)}">
										{latestLabel(item)}
									</div>
									<div class="mt-1 text-[11px] text-gray-500 dark:text-gray-400 whitespace-nowrap">
										{#if item.latest?.latency_ms}
											{item.latest.latency_ms} ms
										{:else}
											-
										{/if}
									</div>
								</div>
							</div>

							<div class="mt-3 grid grid-cols-2 gap-3 text-[11px]">
								<div>
									<div class="text-gray-500 dark:text-gray-400 whitespace-nowrap">
										{$i18n.t('Uptime')}
									</div>
									<div class="mt-1 font-medium text-gray-900 dark:text-white whitespace-nowrap">
										{formatPercent(item.uptime_ratio_90d)}
									</div>
								</div>
								<div>
									<div class="text-gray-500 dark:text-gray-400 whitespace-nowrap">
										{$i18n.t('Last run')}
									</div>
									<div class="mt-1 font-medium text-gray-900 dark:text-white">
										{formatDateTime(item.latest?.checked_at)}
									</div>
								</div>
							</div>

							<div class="mt-3 overflow-x-auto pb-1">
								<div class="w-max min-w-full">
									<div class="flex items-center gap-[3px]" dir={normalizeChatDirection('ltr')}>
										{#each item.history as bucket}
											<Tooltip content={bucketTooltip(bucket)} placement="top">
												<div
													class="h-7 w-1.5 shrink-0 rounded-full {bucketClassName(bucket)}"
												></div>
											</Tooltip>
										{/each}
									</div>
									<div
										class="mt-2 flex items-center gap-2 text-[11px] text-gray-500 dark:text-gray-400 whitespace-nowrap"
									>
										<span>{health.history_window_days} {$i18n.t('days ago')}</span>
										<div class="h-px flex-1 bg-gray-100 dark:bg-gray-800"></div>
										<span>{$i18n.t('Today')}</span>
									</div>
								</div>
							</div>

							{#if item.latest?.error}
								<div class="mt-3 text-[11px] text-red-500">{item.latest.error}</div>
							{/if}
						</div>
					{/each}
				</div>

				<div class="hidden md:block overflow-x-auto">
					<table
						class="w-full min-w-[980px] text-sm text-left text-gray-500 dark:text-gray-400 {loading
							? 'opacity-20'
							: ''}"
					>
						<thead class="text-xs text-gray-800 uppercase bg-transparent dark:text-gray-200">
							<tr class="border-b-[1.5px] border-gray-50 dark:border-gray-850/30">
								<th
									scope="col"
									class="px-2.5 py-2 cursor-pointer select-none"
									on:click={() => toggleSort('name')}
								>
									<div class="flex gap-1.5 items-center whitespace-nowrap">
										{$i18n.t('Model')}
										{#if sortBy === 'name'}
											{#if direction === 'asc'}<ChevronUp className="size-2" />{:else}<ChevronDown
													className="size-2"
												/>{/if}
										{/if}
									</div>
								</th>
								<th
									scope="col"
									class="px-2.5 py-2 cursor-pointer select-none"
									on:click={() => toggleSort('status')}
								>
									<div class="flex gap-1.5 items-center whitespace-nowrap">
										{$i18n.t('Status')}
										{#if sortBy === 'status'}
											{#if direction === 'asc'}<ChevronUp className="size-2" />{:else}<ChevronDown
													className="size-2"
												/>{/if}
										{/if}
									</div>
								</th>
								<th
									scope="col"
									class="px-2.5 py-2 text-right cursor-pointer select-none"
									on:click={() => toggleSort('uptime')}
								>
									<div class="flex gap-1.5 items-center justify-end whitespace-nowrap">
										{$i18n.t('Uptime')}
										{#if sortBy === 'uptime'}
											{#if direction === 'asc'}<ChevronUp className="size-2" />{:else}<ChevronDown
													className="size-2"
												/>{/if}
										{/if}
									</div>
								</th>
								<th
									scope="col"
									class="px-2.5 py-2 text-right cursor-pointer select-none"
									on:click={() => toggleSort('latency')}
								>
									<div class="flex gap-1.5 items-center justify-end whitespace-nowrap">
										{$i18n.t('Latency')}
										{#if sortBy === 'latency'}
											{#if direction === 'asc'}<ChevronUp className="size-2" />{:else}<ChevronDown
													className="size-2"
												/>{/if}
										{/if}
									</div>
								</th>
								<th scope="col" class="px-2.5 py-2 min-w-[430px] whitespace-nowrap"
									>{$i18n.t('History')}</th
								>
							</tr>
						</thead>
						<tbody>
							{#each visibleModels as item (item.id)}
								<tr
									class="bg-white dark:bg-gray-900 text-xs hover:bg-gray-50 dark:hover:bg-gray-850/50 transition"
								>
									<td class="px-3 py-2 align-top">
										<div class="flex items-start gap-2.5">
											<img
												src={`${WEBUI_API_BASE_URL}/models/model/profile/image?id=${item.id}`}
												alt={item.name}
												class="mt-0.5 size-7 rounded-full object-cover shrink-0"
												on:error={(e) => {
													(e.currentTarget as HTMLImageElement).src = '/favicon.png';
												}}
											/>
											<div class="flex flex-col gap-0.5 min-w-0">
												<span class="font-medium text-gray-800 dark:text-gray-200">{item.name}</span
												>
												<span class="text-[11px] text-gray-500 dark:text-gray-400 whitespace-nowrap"
													>{item.provider ?? $i18n.t('Model')}</span
												>
											</div>
										</div>
									</td>
									<td class="px-3 py-2 align-top">
										<div class="flex flex-col gap-0.5">
											<span class="font-medium whitespace-nowrap {latestColorClass(item)}"
												>{latestLabel(item)}</span
											>
											<span class="text-[11px] text-gray-500 dark:text-gray-400"
												>{formatDateTime(item.latest?.checked_at)}</span
											>
										</div>
									</td>
									<td
										class="px-3 py-2 text-right align-top font-medium text-gray-900 dark:text-white whitespace-nowrap"
										>{formatPercent(item.uptime_ratio_90d)}</td
									>
									<td
										class="px-3 py-2 text-right align-top font-medium text-gray-900 dark:text-white whitespace-nowrap"
									>
										{#if item.latest?.latency_ms}
											{item.latest.latency_ms} ms
										{:else}
											<span class="text-gray-400">-</span>
										{/if}
									</td>
									<td class="px-3 py-2 align-top">
										<div class="min-w-[430px]">
											<div class="flex items-center gap-[3px]" dir={normalizeChatDirection('ltr')}>
												{#each item.history as bucket}
													<Tooltip content={bucketTooltip(bucket)} placement="top">
														<div class="h-8 w-1.5 rounded-full {bucketClassName(bucket)}"></div>
													</Tooltip>
												{/each}
											</div>
											<div
												class="mt-2 flex items-center gap-2 text-[11px] text-gray-500 dark:text-gray-400 whitespace-nowrap"
											>
												<span>{health.history_window_days} {$i18n.t('days ago')}</span>
												<div class="h-px flex-1 bg-gray-100 dark:bg-gray-800"></div>
												<span>{$i18n.t('Today')}</span>
											</div>
											{#if item.latest?.error}
												<div class="mt-2 text-[11px] text-red-500 line-clamp-2">
													{item.latest.error}
												</div>
											{/if}
										</div>
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{:else if !loading}
				<div class="text-center text-xs text-gray-500 py-8">
					{$i18n.t('No matching models found')}
				</div>
			{/if}
		</div>

		{#if health && health.models.length > 0}
			<div class="text-gray-500 text-xs mt-1.5 w-full flex justify-end">
				<div class="text-right">
					{$i18n.t('Hourly probe results kept for the last {{DAYS}} days.', {
						DAYS: health.history_window_days
					})}
				</div>
			</div>
		{/if}
	</div>
</div>
