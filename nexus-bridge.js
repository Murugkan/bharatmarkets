const NEXUS_BRIDGE = {
    async syncToCloud() {
        const symbols = localStorage.getItem('onyx_symbols');
        const token = localStorage.getItem('gh_token'); // Ensure PAT is in localStorage
        
        // 1. Get SHA of existing symbols.json
        const url = `https://api.github.com/repos/YOUR_USER/YOUR_REPO/contents/symbols.json`;
        const fileRef = await fetch(url, { headers: { 'Authorization': `token ${token}` } });
        const { sha } = await fileRef.json();

        // 2. Push updated JSON
        const push = await fetch(url, {
            method: 'PUT',
            headers: { 'Authorization': `token ${token}`, 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: "Nexus: Update symbols.json",
                content: btoa(unescape(encodeURIComponent(symbols))),
                sha: sha
            })
        });

        if (push.ok) console.log("✅ GitHub Updated");
    }
};
