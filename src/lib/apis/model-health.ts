import { WEBUI_BASE_URL } from '$lib/constants';

export const getPublicModelHealth = async () => {
	let error = null;
	const token = typeof localStorage !== 'undefined' ? (localStorage.getItem('token') ?? '') : '';

	const res = await fetch(`${WEBUI_BASE_URL}/api/model-health`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			...(token ? { authorization: `Bearer ${token}` } : {})
		},
		credentials: 'same-origin'
	})
		.then(async (response) => {
			if (!response.ok) {
				throw await response.json();
			}

			return response.json();
		})
		.catch((err) => {
			error = err;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};
