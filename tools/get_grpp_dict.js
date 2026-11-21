async function extractGrppStations() {
    const res = await fetch('https://eaudioplayer.radio-grpp.io/static/dist/last/js/app.js?v=20160630203376');
    const text = await res.text();
    // find all occurrences of name: "..." and media: "..."
    const regex = /{\s*name:\s*"([^"]+)",\s*media:\s*"([^"]+)"/g;
    let m;
    while ((m = regex.exec(text)) !== null) {
        console.log(`Station: ${m[1]} -> Media ID: ${m[2]}`);
    }
}
extractGrppStations();
