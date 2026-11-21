async function checkGrppApp() {
    const res = await fetch('https://eaudioplayer.radio-grpp.io/static/dist/last/js/app.js?v=20160630203376');
    const text = await res.text();
    // Look for oxigeno, studio92, lazona
    const matches = text.match(/[a-f0-9]{24}/g) || [];
    console.log("Found hex ids in grpp app.js:", [...new Set(matches)]);
    // Also search for "oxigeno"
    let idx = text.indexOf('oxigeno');
    while (idx !== -1) {
        console.log("Oxigeno context:", text.slice(Math.max(0, idx - 50), idx + 100));
        idx = text.indexOf('oxigeno', idx + 1);
        if (idx > 5000) break;
    }
}
checkGrppApp();
