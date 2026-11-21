// Test script: connects to each stream with ffprobe for 3 seconds to check status
import { exec } from 'child_process';
import util from 'util';

const execPromise = util.promisify(exec);

const streams = [
    { name: 'Onda Cero', url: 'https://mdstrm.com/audio/6598b65ab398c90871aff8cc/icecast.audio' },
    { name: 'Panamericana', url: 'https://mdstrm.com/audio/6598b62dded1380470f4e539/icecast.audio' },
    { name: 'Studio 92', url: 'https://mdstrm.com/audio/5fada553978fe1080e3ac5ea/icecast.audio' },
    { name: 'Viva FM', url: 'https://tupanel.info:8780/stream' },
    { name: 'La Zona', url: 'https://mdstrm.com/audio/5fada54116646e098d97e6a5/live.m3u8' }
];

async function testStreams() {
    console.log("Testing streams with ffprobe (timeout 6s)...");
    for (const s of streams) {
        try {
            console.log(`\nTesting ${s.name} (${s.url})...`);
            const cmd = `ffprobe -v error -show_entries stream=codec_name,sample_rate,channels,bit_rate -of json "${s.url}"`;
            const { stdout } = await execPromise(cmd, { timeout: 8000 });
            console.log(`[SUCCESS] ${s.name}:`);
            console.log(stdout.trim());
        } catch (e) {
            console.log(`[FAILED] ${s.name}: ${e.message.split('\n')[0]}`);
        }
    }
}

testStreams();
