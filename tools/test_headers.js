// Test if X-Forwarded-For or Referer disables pre-roll ads
async function testHeaders() {
    const url = 'https://mdstrm.com/audio/6839e1c82cc4c480fcd318dd/live.m3u8?dnt=true';
    const headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://www.oigo.com/moda/radioenvivo/',
        'Origin': 'https://www.oigo.com',
        'X-Forwarded-For': '190.232.128.5', // Lima, Peru IP
        'X-Real-IP': '190.232.128.5'
    };

    console.log("Fetching with Peruvian headers...");
    const res1 = await fetch(url, { headers });
    const text1 = await res1.text();
    const chunkUrl = text1.match(/https?:\/\/[^\s]+/)?.[0];
    if (!chunkUrl) {
        console.log("No chunklist url found in master:", text1);
        return;
    }

    console.log("Chunklist URL:", chunkUrl);
    const res2 = await fetch(chunkUrl, { headers });
    const text2 = await res2.text();
    console.log("--- CHUNKLIST FIRST 500 CHARS ---");
    console.log(text2.slice(0, 500));
    
    if (text2.includes('X-AD-ID') || text2.includes('/ad_')) {
        console.log("\n[RESULT] Ad is STILL present despite X-Forwarded-For.");
    } else {
        console.log("\n[RESULT] SUCCESS! No ads found with Peruvian headers!");
    }
}

testHeaders();
