<script lang="ts">
	import { marked } from 'marked';
	import fileSaver from 'file-saver';
	const { saveAs } = fileSaver;

	import { onMount, getContext, tick } from 'svelte';
	const i18n = getContext('i18n');

	import { WEBUI_NAME, config, mobile, models as _models, settings, user } from '$lib/stores';
	import {
		createNewModel,
		deleteAllModels,
		getBaseModels,
		toggleModelById,
		updateModelById,
		importModels
	} from '$lib/apis/models';
	import { getGroups } from '$lib/apis/groups';
	import { copyToClipboard } from '$lib/utils';
	import { page } from '$app/stores';
	import { updateUserSettings } from '$lib/apis/users';

	import { getModels } from '$lib/apis';
	import Search from '$lib/components/icons/Search.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Switch from '$lib/components/common/Switch.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';

	import ModelEditor from '$lib/components/workspace/Models/ModelEditor.svelte';
	import { toast } from 'svelte-sonner';
	import Badge from '$lib/components/common/Badge.svelte';
	import ConfirmDialog from '$lib/components/common/ConfirmDialog.svelte';
	import Cog6 from '$lib/components/icons/Cog6.svelte';
	import ModelSettingsModal from './Models/ModelSettingsModal.svelte';
	import Wrench from '$lib/components/icons/Wrench.svelte';
	import Download from '$lib/components/icons/Download.svelte';
	import ManageModelsModal from './Models/ManageModelsModal.svelte';
	import ModelMenu from '$lib/components/admin/Settings/Models/ModelMenu.svelte';
	import EllipsisHorizontal from '$lib/components/icons/EllipsisHorizontal.svelte';
	import EyeSlash from '$lib/components/icons/EyeSlash.svelte';
	import Eye from '$lib/components/icons/Eye.svelte';
	import CheckCircle from '$lib/components/icons/CheckCircle.svelte';
	import Minus from '$lib/components/icons/Minus.svelte';
	import { WEBUI_API_BASE_URL, WEBUI_BASE_URL } from '$lib/constants';
	import { goto } from '$app/navigation';
	import { DropdownMenu } from 'bits-ui';
	import { flyAndScale } from '$lib/utils/transitions';
	import Dropdown from '$lib/components/common/Dropdown.svelte';
	import AdminViewSelector from './Models/AdminViewSelector.svelte';
	import Pagination from '$lib/components/common/Pagination.svelte';

	let shiftKey = false;

	let modelsImportInProgress = false;
	let importFiles;
	let modelsImportInputElement: HTMLInputElement;
	let batchIconFiles;
	let batchIconInputElement: HTMLInputElement;
	let batchActionInProgress = false;
	let batchIconPreviewUrl = '';

	let models = null;

	let workspaceModels = null;
	let baseModels = null;
	let groups = [];

	let filteredModels = [];
	let selectedModelId = null;
	let selectedModelIds: string[] = [];
	let lastSelectedModelId: string | null = null;

	let showConfigModal = false;
	let showManageModal = false;

	let viewOption = ''; // '' = All, 'enabled', 'disabled', 'visible', 'hidden'
	let batchAccessMode = 'private';
	let batchGroupId = '';
	let batchNameTemplate = '{name}';
	let filterSignature = '';
	let allFilteredSelected = false;
	let selectedCountLabel = '';

	const perPage = 30;
	let currentPage = 1;

	const isPublicModel = (model) => {
		return (model?.access_grants ?? []).some(
			(g) => g.principal_type === 'user' && g.principal_id === '*' && g.permission === 'read'
		);
	};

	$: if (models) {
		filteredModels = models
			.filter((m) => searchValue === '' || m.name.toLowerCase().includes(searchValue.toLowerCase()))
			.filter((m) => {
				if (viewOption === 'enabled') return m?.is_active ?? true;
				if (viewOption === 'disabled') return !(m?.is_active ?? true);
				if (viewOption === 'visible') return !(m?.meta?.hidden ?? false);
				if (viewOption === 'hidden') return m?.meta?.hidden === true;
				if (viewOption === 'public') return isPublicModel(m);
				if (viewOption === 'private') return !isPublicModel(m);
				return true; // All
			});
	}

	let searchValue = '';

	$: {
		const nextSignature = JSON.stringify({ searchValue, viewOption });
		if (nextSignature !== filterSignature) {
			currentPage = 1;
			filterSignature = nextSignature;
		}
	}

	$: if (models) {
		const modelIds = new Set(models.map((model) => model.id));
		const nextSelectedModelIds = selectedModelIds.filter((id) => modelIds.has(id));
		if (nextSelectedModelIds.length !== selectedModelIds.length) {
			selectedModelIds = nextSelectedModelIds;
		}

		if (lastSelectedModelId && !modelIds.has(lastSelectedModelId)) {
			lastSelectedModelId = null;
		}
	}

	$: allFilteredSelected =
		filteredModels.length > 0 &&
		filteredModels.every((model) => selectedModelIds.includes(model.id));
	$: selectedCountLabel = $i18n.t('{{COUNT}} models', { COUNT: selectedModelIds.length });
	$: if (!batchGroupId && groups.length > 0) {
		batchGroupId = groups[0].id;
	}

	const syncModelsStore = async () => {
		_models.set(
			await getModels(
				localStorage.token,
				$config?.features?.enable_direct_connections && ($settings?.directConnections ?? null)
			)
		);
	};

	const setModelSelection = (modelId: string, shiftPressed = false) => {
		const alreadySelected = selectedModelIds.includes(modelId);

		if (shiftPressed && lastSelectedModelId) {
			const orderedIds = filteredModels.map((model) => model.id);
			const start = orderedIds.indexOf(lastSelectedModelId);
			const end = orderedIds.indexOf(modelId);

			if (start !== -1 && end !== -1) {
				const [min, max] = start < end ? [start, end] : [end, start];
				const rangeIds = orderedIds.slice(min, max + 1);

				if (alreadySelected) {
					selectedModelIds = selectedModelIds.filter((id) => !rangeIds.includes(id));
				} else {
					selectedModelIds = [...new Set([...selectedModelIds, ...rangeIds])];
				}
			} else if (alreadySelected) {
				selectedModelIds = selectedModelIds.filter((id) => id !== modelId);
			} else {
				selectedModelIds = [...selectedModelIds, modelId];
			}
		} else if (alreadySelected) {
			selectedModelIds = selectedModelIds.filter((id) => id !== modelId);
		} else {
			selectedModelIds = [...selectedModelIds, modelId];
		}

		lastSelectedModelId = modelId;
	};

	const toggleSelectAllFilteredModels = () => {
		const filteredIds = filteredModels.map((model) => model.id);
		const shouldUnselect = filteredIds.every((id) => selectedModelIds.includes(id));

		if (shouldUnselect) {
			selectedModelIds = selectedModelIds.filter((id) => !filteredIds.includes(id));
			return;
		}

		selectedModelIds = [...new Set([...selectedModelIds, ...filteredIds])];
	};

	const clearSelection = () => {
		selectedModelIds = [];
		lastSelectedModelId = null;
		batchIconPreviewUrl = '';
	};

	const selectedModels = () => {
		const selectedIds = new Set(selectedModelIds);
		return (models ?? []).filter((model) => selectedIds.has(model.id));
	};

	const selectedModelsInDisplayOrder = () => {
		const selectedIds = new Set(selectedModelIds);
		return filteredModels.filter((model) => selectedIds.has(model.id));
	};

	const openModelEditorInNewTab = (modelId: string) => {
		const url = new URL(window.location.href);
		url.searchParams.set('id', modelId);
		url.searchParams.set('close_on_save', '1');
		window.open(url.toString(), '_blank');
	};

	const shouldCloseOnSave = () => $page.url.searchParams.get('close_on_save') === '1';

	const closeWindowIfRequested = async () => {
		if (!shouldCloseOnSave()) {
			return false;
		}

		try {
			window.close();
		} catch (error) {
			console.error(error);
			return false;
		}

		await tick();
		if (!window.closed) {
			const url = new URL(window.location.href);
			url.searchParams.delete('close_on_save');
			window.history.replaceState({}, '', url.toString());
		}
		return window.closed;
	};

	const persistModel = async (model, showSuccessToast = false) => {
		model.base_model_id = null;

		if (workspaceModels.find((m) => m.id === model.id)) {
			const res = await updateModelById(localStorage.token, model.id, model).catch(() => {
				return null;
			});

			if (res && showSuccessToast) {
				toast.success($i18n.t('Model updated successfully'));
			}

			return !!res;
		}

		const res = await createNewModel(localStorage.token, {
			meta: {},
			id: model.id,
			name: model.name,
			base_model_id: null,
			params: {},
			access_grants: [],
			...model
		}).catch(() => {
			return null;
		});

		if (res && showSuccessToast) {
			toast.success($i18n.t('Model updated successfully'));
		}

		return !!res;
	};

	const enableAllHandler = async () => {
		const modelsToEnable = filteredModels.filter((m) => !(m.is_active ?? true));
		await Promise.all(modelsToEnable.map((model) => setModelEnabledState(model, true, false)));
		await syncModelsStore();
	};

	const disableAllHandler = async () => {
		const modelsToDisable = filteredModels.filter((m) => m.is_active ?? true);
		await Promise.all(modelsToDisable.map((model) => setModelEnabledState(model, false, false)));
		await syncModelsStore();
	};

	const showAllHandler = async () => {
		const modelsToShow = filteredModels.filter((m) => m?.meta?.hidden === true);
		// Optimistic UI update
		modelsToShow.forEach((m) => {
			m.meta = { ...m.meta, hidden: false };
		});
		models = models;
		// Sync with server
		await Promise.all(modelsToShow.map((model) => upsertModelHandler(model, false)));
		toast.success($i18n.t('All models are now visible'));
	};

	const hideAllHandler = async () => {
		const modelsToHide = filteredModels.filter((m) => !(m?.meta?.hidden ?? false));
		// Optimistic UI update
		modelsToHide.forEach((m) => {
			m.meta = { ...m.meta, hidden: true };
		});
		models = models;
		// Sync with server
		await Promise.all(modelsToHide.map((model) => upsertModelHandler(model, false)));
		toast.success($i18n.t('All models are now hidden'));
	};

	const downloadModels = async (models) => {
		let blob = new Blob([JSON.stringify(models)], {
			type: 'application/json'
		});
		saveAs(blob, `models-export-${Date.now()}.json`);
	};

	const init = async () => {
		models = null;

		workspaceModels = await getBaseModels(localStorage.token);
		baseModels = await getModels(localStorage.token, null, true);

		models = baseModels.map((m) => {
			const workspaceModel = workspaceModels.find((wm) => wm.id === m.id);

			if (workspaceModel) {
				return {
					...m,
					...workspaceModel
				};
			} else {
				return {
					...m,
					id: m.id,
					name: m.name,

					is_active: true
				};
			}
		});
	};

	const upsertModelHandler = async (model, showSuccessToast = true) => {
		const success = await persistModel(model, showSuccessToast);
		if (!success) return false;

		await init();
		await syncModelsStore();
		return true;
	};

	const toggleModelHandler = async (model, shouldSync = true) => {
		if (!Object.keys(model).includes('base_model_id')) {
			const res = await createNewModel(localStorage.token, {
				id: model.id,
				name: model.name,
				base_model_id: null,
				meta: {},
				params: {},
				access_grants: [],
				is_active: model.is_active
			}).catch(() => {
				return null;
			});

			if (!res) {
				return false;
			}
		} else {
			const res = await toggleModelById(localStorage.token, model.id).catch(() => {
				return null;
			});

			if (!res) {
				return false;
			}
		}

		if (shouldSync) {
			await syncModelsStore();
		}

		return true;
	};

	const setModelEnabledState = async (model, enabled: boolean, shouldSync = true) => {
		const currentState = model?.is_active ?? true;
		if (currentState === enabled) {
			return true;
		}

		model.is_active = enabled;
		return await toggleModelHandler(model, shouldSync);
	};

	const runBatchUpdate = async (handler: Function, successMessage: string) => {
		if (batchActionInProgress || selectedModelIds.length === 0) {
			return;
		}

		batchActionInProgress = true;

		try {
			const updatedCount = await handler();

			if (updatedCount > 0) {
				await init();
				await syncModelsStore();
				toast.success(successMessage);
			}

			// Clear selection after batch actions complete to avoid accidental repeat actions.
			clearSelection();
		} catch (error) {
			toast.error(error?.detail ?? `${error}`);
		} finally {
			batchActionInProgress = false;
		}
	};

	const batchEnableDisableHandler = async (enabled: boolean) => {
		await runBatchUpdate(
			async () => {
				let updatedCount = 0;

				for (const model of selectedModels()) {
					const updated = await setModelEnabledState(model, enabled, false);
					if (updated) {
						updatedCount += 1;
					}
				}

				return updatedCount;
			},
			enabled
				? $i18n.t('Selected models enabled successfully')
				: $i18n.t('Selected models disabled successfully')
		);
	};

	const batchAccessGrants = () => {
		if (batchAccessMode === 'public') {
			return [
				{
					principal_type: 'user',
					principal_id: '*',
					permission: 'read'
				}
			];
		}

		if (batchAccessMode === 'group') {
			if (!batchGroupId) {
				return null;
			}

			return [
				{
					principal_type: 'group',
					principal_id: batchGroupId,
					permission: 'read'
				}
			];
		}

		return [];
	};

	const applyBatchAccess = async () => {
		const grants = batchAccessGrants();
		if (grants === null) {
			toast.error($i18n.t('Select a group'));
			return;
		}

		await runBatchUpdate(async () => {
			let updatedCount = 0;

			for (const model of selectedModels()) {
				model.access_grants = JSON.parse(JSON.stringify(grants));
				const updated = await persistModel(model, false);
				if (updated) {
					updatedCount += 1;
				}
			}

			return updatedCount;
		}, $i18n.t('Selected models access updated successfully'));
	};

	const applyBatchNameTemplate = async () => {
		const template = batchNameTemplate.trim();
		if (template === '') {
			toast.error($i18n.t('Name template is required'));
			return;
		}

		await runBatchUpdate(async () => {
			let updatedCount = 0;
			for (const [index, model] of selectedModelsInDisplayOrder().entries()) {
				const nextName = template
					.replaceAll('{name}', model.name ?? model.id)
					.replaceAll('{id}', model.id)
					.replaceAll('{index}', `${index + 1}`)
					.trim();

				if (nextName === '' || nextName === model.name) {
					continue;
				}

				model.name = nextName;
				const updated = await persistModel(model, false);
				if (updated) {
					updatedCount += 1;
				}
			}

			return updatedCount;
		}, $i18n.t('Selected models renamed successfully'));
	};

	const applyBatchIcon = async (profileImageUrl: string) => {
		await runBatchUpdate(async () => {
			let updatedCount = 0;
			for (const model of selectedModels()) {
				model.meta = {
					...model.meta,
					profile_image_url: profileImageUrl
				};

				const updated = await persistModel(model, false);
				if (updated) {
					updatedCount += 1;
				}
			}

			return updatedCount;
		}, $i18n.t('Selected models icon updated successfully'));
	};

	const uploadBatchIcon = async () => {
		if (!batchIconPreviewUrl) {
			toast.error($i18n.t('Select an icon'));
			return;
		}

		await applyBatchIcon(batchIconPreviewUrl);
	};

	const fileToDataUrl = async (file: File) =>
		await new Promise<string>((resolve, reject) => {
			const reader = new FileReader();
			reader.onload = (event) => {
				resolve(String(event.target?.result ?? ''));
			};
			reader.onerror = () => {
				reject(new Error('Failed to read file'));
			};
			reader.readAsDataURL(file);
		});

	const handleBatchIconChange = async () => {
		const file = batchIconFiles?.[0];
		if (!file) {
			return;
		}

		try {
			if (!file.type.startsWith('image/')) {
				toast.error($i18n.t('Invalid file type'));
				return;
			}

			const imageDataUrl = await fileToDataUrl(file);
			batchIconPreviewUrl = imageDataUrl;
		} catch (error) {
			toast.error(error?.detail ?? `${error}`);
		} finally {
			batchIconFiles = null;
			if (batchIconInputElement) {
				batchIconInputElement.value = '';
			}
		}
	};

	const hideModelHandler = async (model) => {
		model.meta = {
			...model.meta,
			hidden: !(model?.meta?.hidden ?? false)
		};

		console.debug(model);

		upsertModelHandler(model, false);

		toast.success(
			model.meta.hidden
				? $i18n.t(`Model {{name}} is now hidden`, {
						name: model.id
					})
				: $i18n.t(`Model {{name}} is now visible`, {
						name: model.id
					})
		);
	};

	const copyLinkHandler = async (model) => {
		const baseUrl = window.location.origin;
		const res = await copyToClipboard(`${baseUrl}/?model=${encodeURIComponent(model.id)}`);

		if (res) {
			toast.success($i18n.t('Copied link to clipboard'));
		} else {
			toast.error($i18n.t('Failed to copy link'));
		}
	};

	const cloneHandler = async (model) => {
		sessionStorage.model = JSON.stringify({
			...model,
			base_model_id: model.id,
			id: `${model.id}-clone`,
			name: `${model.name} (Clone)`
		});
		goto('/workspace/models/create');
	};

	const exportModelHandler = async (model) => {
		let blob = new Blob([JSON.stringify([model])], {
			type: 'application/json'
		});
		saveAs(blob, `${model.id}-${Date.now()}.json`);
	};

	const pinModelHandler = async (modelId) => {
		let pinnedModels = $settings?.pinnedModels ?? [];

		if (pinnedModels.includes(modelId)) {
			pinnedModels = pinnedModels.filter((id) => id !== modelId);
		} else {
			pinnedModels = [...new Set([...pinnedModels, modelId])];
		}

		settings.set({ ...$settings, pinnedModels: pinnedModels });
		await updateUserSettings(localStorage.token, { ui: $settings });
	};

	const openModelEditor = (modelId: string) => {
		selectedModelId = modelId;
	};

	const onModelSave = async (model) => {
		const updated = await upsertModelHandler(model);
		if (!updated) return;

		if (await closeWindowIfRequested()) {
			return;
		}

		selectedModelId = null;
	};

	onMount(async () => {
		await init();
		groups = await getGroups(localStorage.token, true).catch((error) => {
			console.error(error);
			return [];
		});

		const id = $page.url.searchParams.get('id');

		if (id) {
			selectedModelId = id;
		}

		const onKeyDown = (event) => {
			if (event.key === 'Shift') {
				shiftKey = true;
			}
		};

		const onKeyUp = (event) => {
			if (event.key === 'Shift') {
				shiftKey = false;
			}
		};

		const onBlur = () => {
			shiftKey = false;
		};

		window.addEventListener('keydown', onKeyDown);
		window.addEventListener('keyup', onKeyUp);
		window.addEventListener('blur-sm', onBlur);

		return () => {
			window.removeEventListener('keydown', onKeyDown);
			window.removeEventListener('keyup', onKeyUp);
			window.removeEventListener('blur-sm', onBlur);
		};
	});
</script>

<ModelSettingsModal bind:show={showConfigModal} initHandler={init} />
<ManageModelsModal bind:show={showManageModal} />

{#if models !== null}
	{#if selectedModelId === null}
		<div class="flex flex-col gap-1 mt-1.5 mb-2">
			<div class="flex justify-between items-center">
				<div class="flex items-center md:self-center text-xl font-medium px-0.5 gap-2 shrink-0">
					<div>
						{$i18n.t('Models')}
					</div>

					<div class="text-lg font-medium text-gray-500 dark:text-gray-500">
						{filteredModels.length}
					</div>
				</div>

				<div class="flex w-full justify-end gap-1.5">
					{#if $user?.role === 'admin'}
						<input
							id="models-import-input"
							bind:this={modelsImportInputElement}
							bind:files={importFiles}
							type="file"
							accept=".json"
							hidden
							on:change={() => {
								if (importFiles.length > 0) {
									const reader = new FileReader();
									reader.onload = async (event) => {
										modelsImportInProgress = true;

										try {
											const models = JSON.parse(String(event.target.result));
											const res = await importModels(localStorage.token, models);

											if (res) {
												toast.success($i18n.t('Models imported successfully'));
												await init();
											} else {
												toast.error($i18n.t('Failed to import models'));
											}
										} catch (e) {
											toast.error(e?.detail ?? $i18n.t('Invalid JSON file'));
											console.error(e);
										}

										modelsImportInProgress = false;
									};
									reader.readAsText(importFiles[0]);
								}
							}}
						/>

						<input
							id="models-batch-icon-input"
							bind:this={batchIconInputElement}
							bind:files={batchIconFiles}
							type="file"
							accept="image/*"
							hidden
							on:change={handleBatchIconChange}
						/>

						<button
							class="flex text-xs items-center space-x-1 px-3 py-1.5 rounded-xl bg-gray-50 hover:bg-gray-100 dark:bg-gray-850 dark:hover:bg-gray-800 dark:text-gray-200 transition"
							disabled={modelsImportInProgress}
							on:click={() => {
								modelsImportInputElement.click();
							}}
						>
							{#if modelsImportInProgress}
								<Spinner className="size-3" />
							{/if}
							<div class=" self-center font-medium line-clamp-1">
								{$i18n.t('Import')}
							</div>
						</button>

						<button
							class="flex text-xs items-center space-x-1 px-3 py-1.5 rounded-xl bg-gray-50 hover:bg-gray-100 dark:bg-gray-850 dark:hover:bg-gray-800 dark:text-gray-200 transition"
							on:click={async () => {
								downloadModels(models);
							}}
						>
							<div class=" self-center font-medium line-clamp-1">
								{$i18n.t('Export')}
							</div>
						</button>
					{/if}

					<button
						class="flex text-xs items-center space-x-1 px-3 py-1.5 rounded-xl bg-gray-50 hover:bg-gray-100 dark:bg-gray-850 dark:hover:bg-gray-800 dark:text-gray-200 transition"
						type="button"
						on:click={() => {
							showManageModal = true;
						}}
					>
						<div class=" self-center font-medium line-clamp-1">
							{$i18n.t('Manage')}
						</div>
					</button>

					<button
						class="flex text-xs items-center space-x-1 px-3 py-1.5 rounded-xl bg-black hover:bg-gray-900 text-white dark:bg-white dark:hover:bg-gray-100 dark:text-black transition font-medium"
						type="button"
						on:click={() => {
							showConfigModal = true;
						}}
					>
						<div class=" self-center font-medium line-clamp-1">
							{$i18n.t('Settings')}
						</div>
					</button>
				</div>
			</div>
		</div>

		<div
			class="py-2 bg-white dark:bg-gray-900 rounded-3xl border border-gray-100/30 dark:border-gray-850/30"
		>
			<div class="px-3.5 flex flex-1 items-center w-full space-x-2 py-0.5 pb-2">
				<div class="flex flex-1 items-center">
					<div class=" self-center ml-1 mr-3">
						<Search className="size-3.5" />
					</div>
					<input
						class=" w-full text-sm py-1 rounded-r-xl outline-hidden bg-transparent"
						bind:value={searchValue}
						placeholder={$i18n.t('Search Models')}
					/>
					{#if searchValue}
						<div class="self-center pl-1.5 translate-y-[0.5px] rounded-l-xl bg-transparent">
							<button
								class="p-0.5 rounded-full hover:bg-gray-100 dark:hover:bg-gray-900 transition"
								on:click={() => {
									searchValue = '';
								}}
							>
								<XMark className="size-3" strokeWidth="2" />
							</button>
						</div>
					{/if}
				</div>
			</div>

			<div class="px-3 flex w-full items-center bg-transparent overflow-x-auto scrollbar-none">
				<div
					class="flex gap-0.5 w-fit text-center text-sm rounded-full bg-transparent whitespace-nowrap"
				>
					<AdminViewSelector bind:value={viewOption} />
				</div>

				<div class="flex-1"></div>

				<label
					class="flex items-center gap-2 mr-2 px-2 py-1 rounded-lg text-xs text-gray-500 dark:text-gray-300 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-850 transition"
				>
					<input
						type="checkbox"
						class="size-3.5 rounded border-gray-300 dark:border-gray-700 bg-transparent"
						checked={allFilteredSelected}
						on:change={toggleSelectAllFilteredModels}
					/>
					{$i18n.t('Select All')}
				</label>

				<Dropdown>
					<Tooltip content={$i18n.t('Actions')}>
						<button
							class="p-1 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition"
							type="button"
						>
							<EllipsisHorizontal className="size-4" />
						</button>
					</Tooltip>

					<div slot="content">
						<DropdownMenu.Content
							class="w-full max-w-[170px] rounded-xl p-1 border border-gray-100 dark:border-gray-800 z-50 bg-white dark:bg-gray-850 dark:text-white shadow-sm"
							sideOffset={-2}
							side="bottom"
							align="end"
							transition={flyAndScale}
						>
							<DropdownMenu.Item
								class="select-none flex gap-2 items-center px-3 py-1.5 text-sm font-medium cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
								on:click={() => {
									enableAllHandler();
								}}
							>
								<CheckCircle className="size-4" />
								<div class="flex items-center">{$i18n.t('Enable All')}</div>
							</DropdownMenu.Item>

							<DropdownMenu.Item
								class="select-none flex gap-2 items-center px-3 py-1.5 text-sm font-medium cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
								on:click={() => {
									disableAllHandler();
								}}
							>
								<Minus className="size-4" />
								<div class="flex items-center">{$i18n.t('Disable All')}</div>
							</DropdownMenu.Item>

							<hr class="border-gray-100 dark:border-gray-800 my-1" />

							<DropdownMenu.Item
								class="select-none flex gap-2 items-center px-3 py-1.5 text-sm font-medium cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
								on:click={() => {
									showAllHandler();
								}}
							>
								<Eye className="size-4" />
								<div class="flex items-center">{$i18n.t('Show All')}</div>
							</DropdownMenu.Item>

							<DropdownMenu.Item
								class="select-none flex gap-2 items-center px-3 py-1.5 text-sm font-medium cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
								on:click={() => {
									hideAllHandler();
								}}
							>
								<EyeSlash className="size-4" />
								<div class="flex items-center">{$i18n.t('Hide All')}</div>
							</DropdownMenu.Item>
						</DropdownMenu.Content>
					</div>
				</Dropdown>
			</div>

			{#if selectedModelIds.length > 0}
				<div class="px-3 mt-2">
					<div
						class="w-full rounded-2xl border border-gray-100 dark:border-gray-850 bg-gray-50/80 dark:bg-gray-900/50 px-3 py-2.5 flex flex-wrap items-center gap-2.5"
					>
						<div class="text-xs font-medium text-gray-500 dark:text-gray-300">
							{selectedCountLabel}
						</div>

						<div class="h-4 w-px bg-gray-200 dark:bg-gray-800"></div>

						<div class="flex items-center gap-1.5">
							<button
								class="text-xs px-2.5 py-1 rounded-lg bg-white hover:bg-gray-100 dark:bg-gray-850 dark:hover:bg-gray-800 transition disabled:opacity-60 disabled:cursor-not-allowed"
								type="button"
								disabled={batchActionInProgress}
								on:click={() => {
									batchEnableDisableHandler(true);
								}}
							>
								{$i18n.t('Enable')}
							</button>

							<button
								class="text-xs px-2.5 py-1 rounded-lg bg-white hover:bg-gray-100 dark:bg-gray-850 dark:hover:bg-gray-800 transition disabled:opacity-60 disabled:cursor-not-allowed"
								type="button"
								disabled={batchActionInProgress}
								on:click={() => {
									batchEnableDisableHandler(false);
								}}
							>
								{$i18n.t('Disable')}
							</button>
						</div>

						<div class="h-4 w-px bg-gray-200 dark:bg-gray-800"></div>

						<div class="flex items-center gap-1.5">
							<select
								class="text-xs px-2 py-1 rounded-lg bg-white dark:bg-gray-850 border border-gray-100 dark:border-gray-800 outline-hidden"
								bind:value={batchAccessMode}
								disabled={batchActionInProgress}
							>
								<option value="private">{$i18n.t('Private')}</option>
								<option value="public">{$i18n.t('Public')}</option>
								<option value="group">{$i18n.t('Group')}</option>
							</select>

							{#if batchAccessMode === 'group'}
								<select
									class="text-xs px-2 py-1 rounded-lg bg-white dark:bg-gray-850 border border-gray-100 dark:border-gray-800 outline-hidden"
									bind:value={batchGroupId}
									disabled={batchActionInProgress}
								>
									{#if groups.length === 0}
										<option value="">{$i18n.t('No groups found')}</option>
									{:else}
										{#each groups as group}
											<option value={group.id}>{group.name}</option>
										{/each}
									{/if}
								</select>
							{/if}

							<button
								class="text-xs px-2.5 py-1 rounded-lg bg-white hover:bg-gray-100 dark:bg-gray-850 dark:hover:bg-gray-800 transition disabled:opacity-60 disabled:cursor-not-allowed"
								type="button"
								disabled={batchActionInProgress || (batchAccessMode === 'group' && !batchGroupId)}
								on:click={applyBatchAccess}
							>
								{$i18n.t('Apply Access')}
							</button>
						</div>

						<div class="h-4 w-px bg-gray-200 dark:bg-gray-800"></div>

						<div class="flex items-center gap-1.5">
							<button
								class="size-8 rounded-lg overflow-hidden bg-white dark:bg-gray-850 border border-gray-100 dark:border-gray-800"
								type="button"
								on:click={() => {
									batchIconInputElement?.click();
								}}
								aria-label={$i18n.t('Select Icon')}
							>
								<img
									src={batchIconPreviewUrl || `${WEBUI_BASE_URL}/static/favicon.png`}
									alt="batch icon preview"
									class="size-full object-cover"
								/>
							</button>

							<button
								class="text-xs px-2.5 py-1 rounded-lg bg-white hover:bg-gray-100 dark:bg-gray-850 dark:hover:bg-gray-800 transition disabled:opacity-60 disabled:cursor-not-allowed"
								type="button"
								disabled={batchActionInProgress}
								on:click={() => {
									batchIconInputElement?.click();
								}}
							>
								{$i18n.t('Select Icon')}
							</button>

							<button
								class="text-xs px-2.5 py-1 rounded-lg bg-white hover:bg-gray-100 dark:bg-gray-850 dark:hover:bg-gray-800 transition disabled:opacity-60 disabled:cursor-not-allowed"
								type="button"
								disabled={batchActionInProgress || !batchIconPreviewUrl}
								on:click={uploadBatchIcon}
							>
								{$i18n.t('Upload Icon')}
							</button>
						</div>

						<div class="h-4 w-px bg-gray-200 dark:bg-gray-800"></div>

						<div class="flex items-center gap-1.5">
							<input
								class="min-w-[180px] text-xs px-2 py-1 rounded-lg bg-white dark:bg-gray-850 border border-gray-100 dark:border-gray-800 outline-hidden"
								type="text"
								bind:value={batchNameTemplate}
								placeholder={$i18n.t('Name template')}
								disabled={batchActionInProgress}
							/>

							<button
								class="text-xs px-2.5 py-1 rounded-lg bg-white hover:bg-gray-100 dark:bg-gray-850 dark:hover:bg-gray-800 transition disabled:opacity-60 disabled:cursor-not-allowed"
								type="button"
								disabled={batchActionInProgress || batchNameTemplate.trim() === ''}
								on:click={applyBatchNameTemplate}
							>
								{$i18n.t('Set Name')}
							</button>
						</div>

						<button
							class="text-xs px-2 py-1 rounded-lg text-gray-600 hover:text-gray-800 dark:text-gray-300 dark:hover:text-white hover:bg-white dark:hover:bg-gray-850 transition ml-auto"
							type="button"
							on:click={clearSelection}
						>
							{$i18n.t('Clear')}
						</button>
					</div>
				</div>
			{/if}

			<div class="px-3 my-2" id="model-list">
				{#if filteredModels.length > 0}
					{#each filteredModels.slice((currentPage - 1) * perPage, currentPage * perPage) as model, modelIdx (`${model.id}-${modelIdx}`)}
						<div
							class=" flex gap-2 w-full px-2 py-2 dark:hover:bg-white/5 hover:bg-black/5 rounded-xl transition {model
								?.meta?.hidden
								? 'opacity-50 dark:opacity-50'
								: ''} {selectedModelIds.includes(model.id)
								? 'bg-black/[0.04] dark:bg-white/[0.06]'
								: ''}"
							id="model-item-{model.id}"
						>
							<div class="self-center shrink-0">
								<input
									type="checkbox"
									class="size-4 rounded border-gray-300 dark:border-gray-700 bg-transparent"
									checked={selectedModelIds.includes(model.id)}
									on:click={(event) => {
										const mouseEvent = event as MouseEvent;
										event.stopPropagation();
										setModelSelection(model.id, mouseEvent.shiftKey);
									}}
								/>
							</div>

							<button
								class=" flex flex-1 text-left space-x-3.5 cursor-pointer w-full"
								type="button"
								on:click={() => {
									openModelEditor(model.id);
								}}
								on:auxclick={(event) => {
									const mouseEvent = event as MouseEvent;
									if (mouseEvent.button === 1) {
										event.preventDefault();
										openModelEditorInNewTab(model.id);
									}
								}}
								on:mousedown={(event) => {
									const mouseEvent = event as MouseEvent;
									if (mouseEvent.button === 1) {
										event.preventDefault();
									}
								}}
							>
								<div class=" self-center w-9">
									<div
										class=" rounded-full object-cover {(model?.is_active ?? true)
											? ''
											: 'opacity-50 dark:opacity-50'} "
									>
										<img
											src={`${WEBUI_API_BASE_URL}/models/model/profile/image?id=${model.id}`}
											alt="modelfile profile"
											class=" rounded-full w-full h-auto object-cover"
										/>
									</div>
								</div>

								<div
									class=" flex-1 self-center {(model?.is_active ?? true) ? '' : 'text-gray-500'}"
								>
									<Tooltip
										content={marked.parse(
											!!model?.meta?.description
												? model?.meta?.description
												: model?.ollama?.digest
													? `${model?.ollama?.digest} **(${model?.ollama?.modified_at})**`
													: model.id
										)}
										className=" w-fit"
										placement="top-start"
									>
										<div class="font-medium line-clamp-1 flex items-center gap-2">
											{model.name}

											<Badge
												type={(model?.access_grants ?? []).some(
													(g) =>
														g.principal_type === 'user' &&
														g.principal_id === '*' &&
														g.permission === 'read'
												)
													? 'success'
													: 'muted'}
												content={(model?.access_grants ?? []).some(
													(g) =>
														g.principal_type === 'user' &&
														g.principal_id === '*' &&
														g.permission === 'read'
												)
													? $i18n.t('Public')
													: $i18n.t('Private')}
											/>
										</div>
									</Tooltip>
									<div
										class=" text-xs overflow-hidden text-ellipsis line-clamp-1 flex items-center gap-1 text-gray-500"
									>
										<span class=" line-clamp-1">
											{!!model?.meta?.description
												? model?.meta?.description
												: model?.ollama?.digest
													? `${model.id} (${model?.ollama?.digest})`
													: model.id}
										</span>
									</div>
								</div>
							</button>
							<div class="flex flex-row gap-0.5 items-center self-center">
								{#if shiftKey}
									<Tooltip content={model?.meta?.hidden ? $i18n.t('Show') : $i18n.t('Hide')}>
										<button
											class="self-center w-fit text-sm px-2 py-2 dark:text-gray-300 dark:hover:text-white hover:bg-black/5 dark:hover:bg-white/5 rounded-xl"
											type="button"
											on:click={() => {
												hideModelHandler(model);
											}}
										>
											{#if model?.meta?.hidden}
												<EyeSlash />
											{:else}
												<Eye />
											{/if}
										</button>
									</Tooltip>
								{:else}
									<button
										class="self-center w-fit text-sm px-2 py-2 dark:text-gray-300 dark:hover:text-white hover:bg-black/5 dark:hover:bg-white/5 rounded-xl"
										type="button"
										on:click={() => {
											openModelEditor(model.id);
										}}
										on:auxclick={(event) => {
											const mouseEvent = event as MouseEvent;
											if (mouseEvent.button === 1) {
												event.preventDefault();
												openModelEditorInNewTab(model.id);
											}
										}}
									>
										<svg
											xmlns="http://www.w3.org/2000/svg"
											fill="none"
											viewBox="0 0 24 24"
											stroke-width="1.5"
											stroke="currentColor"
											class="w-4 h-4"
										>
											<path
												stroke-linecap="round"
												stroke-linejoin="round"
												d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L6.832 19.82a4.5 4.5 0 0 1-1.897 1.13l-2.685.8.8-2.685a4.5 4.5 0 0 1 1.13-1.897L16.863 4.487Zm0 0L19.5 7.125"
											/>
										</svg>
									</button>

									<ModelMenu
										user={$user}
										{model}
										exportHandler={() => {
											exportModelHandler(model);
										}}
										hideHandler={() => {
											hideModelHandler(model);
										}}
										pinModelHandler={() => {
											pinModelHandler(model.id);
										}}
										copyLinkHandler={() => {
											copyLinkHandler(model);
										}}
										cloneHandler={() => {
											cloneHandler(model);
										}}
										onClose={() => {}}
									>
										<button
											class="self-center w-fit text-sm p-1.5 dark:text-gray-300 dark:hover:text-white hover:bg-black/5 dark:hover:bg-white/5 rounded-xl"
											type="button"
										>
											<EllipsisHorizontal className="size-5" />
										</button>
									</ModelMenu>

									<div class="ml-1">
										<Tooltip
											content={(model?.is_active ?? true)
												? $i18n.t('Enabled')
												: $i18n.t('Disabled')}
										>
											<Switch
												bind:state={model.is_active}
												on:change={async () => {
													toggleModelHandler(model);
												}}
											/>
										</Tooltip>
									</div>
								{/if}
							</div>
						</div>
					{/each}
				{:else}
					<div class=" w-full h-full flex flex-col justify-center items-center my-16 mb-24">
						<div class="max-w-md text-center">
							<div class=" text-3xl mb-3">😕</div>
							<div class=" text-lg font-medium mb-1">{$i18n.t('No models found')}</div>
							<div class=" text-gray-500 text-center text-xs">
								{$i18n.t('Try adjusting your search or filter to find what you are looking for.')}
							</div>
						</div>
					</div>
				{/if}
			</div>

			{#if filteredModels.length > perPage}
				<Pagination bind:page={currentPage} count={filteredModels.length} {perPage} />
			{/if}
		</div>
	{:else}
		<ModelEditor
			edit
			model={models.find((m) => m.id === selectedModelId)}
			preset={false}
			onSubmit={onModelSave}
			onBack={async () => {
				selectedModelId = null;
				await init();
			}}
		/>
	{/if}
{:else}
	<div class=" h-full w-full flex justify-center items-center">
		<Spinner className="size-5" />
	</div>
{/if}
