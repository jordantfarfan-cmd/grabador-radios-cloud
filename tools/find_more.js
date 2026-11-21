import https from 'https';

const query = async (url) => {
    return new Promise((resolve) => {
        https.get(url, (res) => {
            let data = '';
            res.on('data', chunk => data += chunk);
            res.on('end', () => {
                try { resolve(JSON.parse(data)); } catch (e) { resolve([]); }
            });
        }).on('error', () => resolve([]));
    });
};

async function main() {
    const stations = await query('https://de1.api.radio-browser.info/json/stations/bycountry/Peru');
    const filtered = stations.filter(s => {
        const n = (s.name || '').toLowerCase();
        return n.includes('oxigeno') || n.includes('moda') || n.includes('planeta') || n.includes('rpp');
    });
    console.log(JSON.stringify(filtered.map(s => ({ name: s.name, url: s.url_resolved || s.url, codec: s.codec })), null, 2));
}

main();
