// Inspect audioplayer.pe HTML scripts and JSON
async function checkOxigeno() {
    const res = await fetch('https://audioplayer.pe/oxigeno', {
        headers: { 'User-Agent': 'Mozilla/5.0' }
    });
    const text = await res.text();
    // Look for __NEXT_DATA__ or any embedded JSON or radio config
    const nextDataMatch = text.match(/<script id="__NEXT_DATA__"[^>]*>([\s\S]*?)<\/script>/);
    if (nextDataMatch) {
        console.log("Found __NEXT_DATA__!");
        const json = JSON.parse(nextDataMatch[1]);
        console.log("NextData keys:", Object.keys(json.props || {}));
        const str = JSON.stringify(json);
        const matches = str.match(/https?:\/\/[^"'\s\\]*(?:mdstrm|m3u8|icecast)[^"'\s\\]*/g) || [];
        console.log("Matches in nextData:", [...new Set(matches)]);
        // Find 24 char hex
        const hex = str.match(/[a-f0-9]{24}/g) || [];
        console.log("Hex ids in nextData:", [...new Set(hex)].slice(0, 10));
    } else {
        console.log("No __NEXT_DATA__, searching for general script content...");
        const scripts = text.match(/<script[^>]*>([\s\S]*?)<\/script>/gi) || [];
        for (const s of scripts) {
            if (s.includes('mdstrm') || s.includes('audio') || s.includes('stream')) {
                console.log("Script snippet:", s.slice(0, 300));
            }
        }
    }
}
checkOxigeno();
