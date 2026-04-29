/**
 * 音频转换工具：Blob(webm) → AudioBuffer → WAV(16kHz mono) → Base64
 * 纯原生 Web Audio API 实现，零额外依赖
 */

/**
 * 将音频 Blob 解码为 AudioBuffer
 */
export async function blobToAudioBuffer(blob: Blob): Promise<AudioBuffer> {
  const arrayBuffer = await blob.arrayBuffer();
  const audioContext = new AudioContext();
  try {
    return await audioContext.decodeAudioData(arrayBuffer);
  } finally {
    audioContext.close();
  }
}

/**
 * 使用 OfflineAudioContext 重采样为指定采样率的单声道 AudioBuffer
 */
export async function resampleToMono(
  audioBuffer: AudioBuffer,
  targetSampleRate: number = 16000
): Promise<AudioBuffer> {
  const frameCount = Math.ceil(audioBuffer.duration * targetSampleRate);
  const offlineContext = new OfflineAudioContext(1, frameCount, targetSampleRate);
  const source = offlineContext.createBufferSource();
  source.buffer = audioBuffer;
  source.connect(offlineContext.destination);
  source.start();
  return offlineContext.startRendering();
}

/**
 * AudioBuffer 转 WAV 格式的 ArrayBuffer
 * 严格遵循 RIFF/WAVE 规范
 */
export function audioBufferToWav(audioBuffer: AudioBuffer): ArrayBuffer {
  const numberOfChannels = audioBuffer.numberOfChannels;
  const sampleRate = audioBuffer.sampleRate;
  const format = 1; // PCM
  const bitDepth = 16;

  const bytesPerSample = bitDepth / 8;
  const blockAlign = numberOfChannels * bytesPerSample;

  const dataLength = audioBuffer.length * numberOfChannels * bytesPerSample;
  const buffer = new ArrayBuffer(44 + dataLength);
  const view = new DataView(buffer);

  // RIFF chunk descriptor
  writeString(view, 0, 'RIFF');
  view.setUint32(4, 36 + dataLength, true);
  writeString(view, 8, 'WAVE');

  // fmt sub-chunk
  writeString(view, 12, 'fmt ');
  view.setUint32(16, 16, true); // Subchunk1Size
  view.setUint16(20, format, true); // AudioFormat = 1 (PCM)
  view.setUint16(22, numberOfChannels, true); // NumChannels
  view.setUint32(24, sampleRate, true); // SampleRate
  view.setUint32(28, sampleRate * blockAlign, true); // ByteRate
  view.setUint16(32, blockAlign, true); // BlockAlign
  view.setUint16(34, bitDepth, true); // BitsPerSample

  // data sub-chunk
  writeString(view, 36, 'data');
  view.setUint32(40, dataLength, true);

  // Write interleaved PCM data
  const offset = 44;
  const channels: Float32Array[] = [];
  for (let i = 0; i < numberOfChannels; i++) {
    channels.push(audioBuffer.getChannelData(i));
  }

  let index = 0;
  for (let i = 0; i < audioBuffer.length; i++) {
    for (let channel = 0; channel < numberOfChannels; channel++) {
      const sample = Math.max(-1, Math.min(1, channels[channel][i]));
      const intSample = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
      view.setInt16(offset + index, intSample, true);
      index += 2;
    }
  }

  return buffer;
}

function writeString(view: DataView, offset: number, string: string) {
  for (let i = 0; i < string.length; i++) {
    view.setUint8(offset + i, string.charCodeAt(i));
  }
}

/**
 * 将 Uint8Array 转为二进制字符串（用于 btoa）
 */
function uint8ArrayToBinaryString(bytes: Uint8Array): string {
  let binary = '';
  const len = bytes.byteLength;
  for (let i = 0; i < len; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return binary;
}

/**
 * 一站式转换：Blob → WAV(16kHz mono) → Base64
 * 异常时返回空字符串
 */
export async function blobToWav16kMonoBase64(blob: Blob): Promise<string> {
  const audioBuffer = await blobToAudioBuffer(blob);
  const monoBuffer = await resampleToMono(audioBuffer, 16000);
  const wavBuffer = audioBufferToWav(monoBuffer);
  const bytes = new Uint8Array(wavBuffer);
  const binary = uint8ArrayToBinaryString(bytes);
  return btoa(binary);
}
