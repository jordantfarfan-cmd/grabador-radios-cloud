import { exec } from 'child_process';
import util from 'util';

const execPromise = util.promisify(exec);

const stations = [
    { name: 'Moda', url: 'https://mdstrm.com/audio/6839e1c82cc4c480fcd318dd/live.m3u8?dnt=true' },
    { name: 'Planeta', url: 'https://mdstrm.com/audio/6839e274f40e6b9832e37633/live.m3u8?dnt=true' },
    { name: 'Onda Cero', url: 'https://mdstrm.com/audio/6598b65ab398c90871aff8cc/live.m3u8?dnt=true' },
    { name: 'Panamericana', url: 'https://mdstrm.com/audio/6598b62dded1380470f4e539/live.m3u8?dnt=true' },
    { name: 'Studio 92', url: 'https://mdstrm.com/audio/5fada553978fe1080e3ac5ea/live.m3u8?dnt=true' },
    { name: 'La Zona', url: 'https://mdstrm.com/audio/5fada54116646e098d97e6a5/live.m3u8?dnt=true' },
    { name: 'Oxigeno', url: 'https://mdstrm.com/audio/5fab0687bcd6c2389ee9480c/live.m3u8?dnt=true' }
];

async function testAllM3u8() {
    console.log("Testing HLS .m3u8?dnt=true for all stations...");
    for (const s of stations) {
        try {
            process.stdout.write(`Checking ${s.name.padEnd(15)} ... `);
            const cmd = `ffprobe -v error -select_streams a:0 -show_entries stream=codec_name,sample_rate,channels -of json "${s.url}"`;
            const { stdout } = await execPromise(cmd, { timeout: 8000 });
            const data = JSON.parse(stdout);
            const stream = data.streams?.[0];
            if (stream) {
                console.log(`[OK] ${stream.codec_name} ${stream.sample_rate}Hz`);
            } else {
                console.log(`[EMPTY]`);
            }
        } catch (e) {
            console.log(`[ERROR] ${e.message.split('\n')[0]}`);
        }
    }
}

testAllM3u8();
