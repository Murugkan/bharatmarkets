const NEXUS_BRIDGE = {
    async syncToCloud() {
        const symbols = localStorage.getItem('onyx_symbols');
        const token = localStorage.getItem('gh_token'); 
        const owner = "YOUR_GITHUB_USERNAME"; // Update this
        const repo = "YOUR_REPO_NAME";       // Update this
        const path = "symbols.json";

        if(!token) { alert("Missing GitHub Token!"); return false; }

        try {
            const url = `https://api.github.com/repos/${owner}/${repo}/contents/${path}`;
            const fileRef = await fetch(url, { headers: { 'Authorization': `token ${token}` } });
            const fileData = await fileRef.json();

            const push = await fetch(url, {
                method: 'PUT',
                headers: { 'Authorization': `token ${token}`, 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: "Nexus Update via iPhone",
                    content: btoa(unescape(encodeURIComponent(symbols))),
                    sha: fileData.sha
                })
            });
            return push.ok;
        } catch (e) { return false; }
    }
};
