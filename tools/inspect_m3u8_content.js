// Fetch and print raw m3u8 content for Moda
async function inspectM3u8() {
    const url = 'https://mdstrm.com/audio/6839e1c82cc4c480fcd318dd/live.m3u8?dnt=true';
    console.log("Fetching master:", url);
    const res1 = await fetch(url);
    const text1 = await res1.text();
    console.log("--- MASTER PLAYLIST ---");
    console.log(text1);

    // If master contains chunklist url
    const chunkUrlMatch = text1.match(/https?:\/\/[^\s]+/);
    if (chunkUrlMatch) {
        console.log("\nFetching chunklist:", chunkUrlMatch[0]);
        const res2 = await fetch(chunkUrlMatch[0]);
        const text2 = await res2.text();
        console.log("--- CHUNKLIST PLAYLIST ---");
        console.log(text2.slice(0, 2000));
    }
}

inspectM3u8();
