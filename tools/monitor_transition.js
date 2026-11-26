// Monitor chunklist over 50 seconds to see the transition from ad_ to live stream
async function monitor() {
    const masterUrl = 'https://mdstrm.com/audio/6839e1c82cc4c480fcd318dd/live.m3u8?dnt=true';
    const res1 = await fetch(masterUrl);
    const text1 = await res1.text();
    const chunkUrl = text1.match(/https?:\/\/[^\s]+/)[0];
    console.log("Chunklist URL:", chunkUrl);

    for (let i = 0; i < 10; i++) {
        const res = await fetch(chunkUrl);
        const text = await res.text();
        const segments = text.match(/https?:\/\/[^\s]+\.aac[^\s]*/g) || [];
        console.log(`[T+${i * 5}s] Segments (${segments.length}):`);
        segments.forEach(s => {
            const isAd = s.includes('/ad_');
            console.log(`   ${isAd ? '[AD]' : '[LIVE]'} ${s.split('?')[0].split('/').slice(-1)[0]}`);
        });
        await new Promise(r => setTimeout(r, 5000));
    }
}
monitor();
