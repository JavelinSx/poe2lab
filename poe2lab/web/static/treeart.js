"use strict";
// The game's own passive-tree art (the tiled background, the class circle, the ascendancy circles) for the tree view.
// PoB ships it as zstd-packed DDS texture arrays in BC7. The server sends the files as they are with
// Content-Encoding: zstd, so the browser unpacks them itself; the layers needed are decoded here into canvases.

// ---------- BC7 (the block format: the D3D11 / Khronos Data Format specification) ----------
// per mode: subsets, partition bits, rotation bits, index-selection bits, colour bits, alpha bits,
// endpoint p-bits, shared p-bits, index bits, second index bits
const BC7_MODES = [
  [3, 4, 0, 0, 4, 0, 1, 0, 3, 0], [2, 6, 0, 0, 6, 0, 0, 1, 3, 0], [3, 6, 0, 0, 5, 0, 0, 0, 2, 0],
  [2, 6, 0, 0, 7, 0, 1, 0, 2, 0], [1, 0, 2, 1, 5, 6, 0, 0, 2, 3], [1, 0, 2, 0, 7, 8, 0, 0, 2, 2],
  [1, 0, 0, 0, 7, 7, 1, 0, 4, 0], [2, 6, 0, 0, 5, 5, 1, 0, 2, 0],
];
// which subset each of the 16 pixels is in: two subsets one bit per pixel, three subsets two bits per pixel
const BC7_P2 = [
  0xCCCC, 0x8888, 0xEEEE, 0xECC8, 0xC880, 0xFEEC, 0xFEC8, 0xEC80, 0xC800, 0xFFEC, 0xFE80, 0xE800, 0xFFE8, 0xFF00, 0xFFF0, 0xF000,
  0xF710, 0x008E, 0x7100, 0x08CE, 0x008C, 0x7310, 0x3100, 0x8CCE, 0x088C, 0x3110, 0x6666, 0x366C, 0x17E8, 0x0FF0, 0x718E, 0x399C,
  0xAAAA, 0xF0F0, 0x5A5A, 0x33CC, 0x3C3C, 0x55AA, 0x9696, 0xA55A, 0x73CE, 0x13C8, 0x324C, 0x3BDC, 0x6996, 0xC33C, 0x9966, 0x0660,
  0x0272, 0x04E4, 0x4E40, 0x2720, 0xC936, 0x936C, 0x39C6, 0x639C, 0x9336, 0x9CC6, 0x817E, 0xE718, 0xCCF0, 0x0FCC, 0x7744, 0xEE22,
];
const BC7_P3 = [
  0xAA685050, 0x6A5A5040, 0x5A5A4200, 0x5450A0A8, 0xA5A50000, 0xA0A05050, 0x5555A0A0, 0x5A5A5050,
  0xAA550000, 0xAA555500, 0xAAAA5500, 0x90909090, 0x94949494, 0xA4A4A4A4, 0xA9A59450, 0x2A0A4250,
  0xA5945040, 0x0A425054, 0xA5A5A500, 0x55A0A0A0, 0xA8A85454, 0x6A6A4040, 0xA4A45000, 0x1A1A0500,
  0x0050A4A4, 0xAAA59090, 0x14696914, 0x69691400, 0xA08585A0, 0xAA821414, 0x50A4A450, 0x6A5A0200,
  0xA9A58000, 0x5090A0A8, 0xA8A09050, 0x24242424, 0x00AA5500, 0x24924924, 0x24499224, 0x50A50A50,
  0x500AA550, 0xAAAA4444, 0x66660000, 0xA5A0A5A0, 0x50A050A0, 0x69286928, 0x44AAAA44, 0x66666600,
  0xAA444444, 0x54A854A8, 0x95809580, 0x96969600, 0xA85454A8, 0x80959580, 0xAA141414, 0x96960000,
  0xAAAA1414, 0xA05050A0, 0xA0A5A5A0, 0x96000000, 0x40804080, 0xA9A8A9A8, 0xAAAAAA44, 0x2A4A5254,
];
// the pixel whose index is stored one bit shorter, per partition: the second subset of two; the second and third of three
const BC7_A2 = [
  15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 2, 8, 2, 2, 8, 8, 15, 2, 8, 2, 2, 8, 8, 2, 2,
  15, 15, 6, 8, 2, 8, 15, 15, 2, 8, 2, 2, 2, 15, 15, 6, 6, 2, 6, 8, 15, 15, 2, 2, 15, 15, 15, 15, 15, 2, 2, 15,
];
const BC7_A3B = [
  3, 3, 15, 15, 8, 3, 15, 15, 8, 8, 6, 6, 6, 5, 3, 3, 3, 3, 8, 15, 3, 3, 6, 10, 5, 8, 8, 6, 8, 5, 15, 15,
  8, 15, 3, 5, 6, 10, 8, 15, 15, 3, 15, 5, 15, 15, 15, 15, 3, 15, 5, 5, 5, 8, 5, 10, 5, 10, 8, 13, 15, 12, 3, 3,
];
const BC7_A3C = [
  15, 8, 8, 3, 15, 15, 3, 8, 15, 15, 15, 15, 15, 15, 15, 8, 15, 8, 15, 3, 15, 8, 15, 8, 3, 15, 6, 10, 15, 15, 10, 8,
  15, 3, 15, 10, 10, 8, 9, 10, 6, 15, 8, 15, 3, 6, 6, 8, 15, 3, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 3, 15, 15, 8,
];
const BC7_W = { 2: [0, 21, 43, 64], 3: [0, 9, 18, 27, 37, 46, 55, 64], 4: [0, 4, 9, 13, 17, 21, 26, 30, 34, 38, 43, 47, 51, 55, 60, 64] };

const bc7Ep = new Int32Array(24);  // up to 6 endpoints x RGBA
const bc7I1 = new Uint8Array(16), bc7I2 = new Uint8Array(16);

// one 16-byte block at `off` into `px` (16 pixels RGBA)
function bc7Block(src, off, px) {
  let pos = 0;
  const read = (n) => {
    let v = 0;
    for (let i = 0; i < n; i++, pos++) v |= ((src[off + (pos >> 3)] >> (pos & 7)) & 1) << i;
    return v;
  };
  let mode = 0;
  while (mode < 8 && !read(1)) mode++;
  if (mode === 8) { px.fill(0); return; }  // reserved mode: transparent black
  const [ns, pb, rb, isbBits, cb, ab, epb, spb, ib, ib2] = BC7_MODES[mode];
  const partition = read(pb), rotation = read(rb), isb = read(isbBits);
  const ne = ns * 2;
  for (let c = 0; c < 3; c++) for (let e = 0; e < ne; e++) bc7Ep[e * 4 + c] = read(cb);
  for (let e = 0; e < ne; e++) bc7Ep[e * 4 + 3] = ab ? read(ab) : 255;
  let cbits = cb, abits = ab;
  if (epb) {
    for (let e = 0; e < ne; e++) {
      const p = read(1);
      for (let c = 0; c < (ab ? 4 : 3); c++) bc7Ep[e * 4 + c] = (bc7Ep[e * 4 + c] << 1) | p;
    }
    cbits++; if (ab) abits++;
  } else if (spb) {
    for (let s = 0; s < ns; s++) {
      const p = read(1);
      for (let e = 2 * s; e < 2 * s + 2; e++) for (let c = 0; c < 3; c++) bc7Ep[e * 4 + c] = (bc7Ep[e * 4 + c] << 1) | p;
    }
    cbits++;
  }
  // to 8 bits: the top bits repeated below
  for (let e = 0; e < ne; e++) {
    for (let c = 0; c < 3; c++) { const v = bc7Ep[e * 4 + c] << (8 - cbits); bc7Ep[e * 4 + c] = v | (v >> cbits); }
    if (ab) { const v = bc7Ep[e * 4 + 3] << (8 - abits); bc7Ep[e * 4 + 3] = v | (v >> abits); }
  }
  const subset = (i) => ns === 1 ? 0 : ns === 2 ? (BC7_P2[partition] >> i) & 1 : (BC7_P3[partition] >>> (2 * i)) & 3;
  const anchor = (s) => s === 0 ? 0 : ns === 2 ? BC7_A2[partition] : s === 1 ? BC7_A3B[partition] : BC7_A3C[partition];
  for (let i = 0; i < 16; i++) bc7I1[i] = read(anchor(subset(i)) === i ? ib - 1 : ib);
  if (ib2) for (let i = 0; i < 16; i++) bc7I2[i] = read(i === 0 ? ib2 - 1 : ib2);
  const w1 = BC7_W[ib], w2 = ib2 ? BC7_W[ib2] : null;
  for (let i = 0; i < 16; i++) {
    const s = subset(i), e0 = s * 8, e1 = e0 + 4;
    // modes 4 and 5 keep colour and alpha indices apart; mode 4's selection bit swaps which set is which
    const cw = w2 ? (isb ? w2[bc7I2[i]] : w1[bc7I1[i]]) : w1[bc7I1[i]];
    const aw = w2 ? (isb ? w1[bc7I1[i]] : w2[bc7I2[i]]) : cw;
    let r = ((64 - cw) * bc7Ep[e0] + cw * bc7Ep[e1] + 32) >> 6;
    let g = ((64 - cw) * bc7Ep[e0 + 1] + cw * bc7Ep[e1 + 1] + 32) >> 6;
    let b = ((64 - cw) * bc7Ep[e0 + 2] + cw * bc7Ep[e1 + 2] + 32) >> 6;
    let a = ((64 - aw) * bc7Ep[e0 + 3] + aw * bc7Ep[e1 + 3] + 32) >> 6;
    if (rotation === 1) [a, r] = [r, a];
    else if (rotation === 2) [a, g] = [g, a];
    else if (rotation === 3) [a, b] = [b, a];
    px[i * 4] = r; px[i * 4 + 1] = g; px[i * 4 + 2] = b; px[i * 4 + 3] = a;
  }
}

function decodeBC7(src, off, width, height) {
  const out = new Uint8ClampedArray(width * height * 4);
  const bw = Math.max(1, (width + 3) >> 2), bh = Math.max(1, (height + 3) >> 2);
  const px = new Uint8Array(64);
  for (let by = 0; by < bh; by++) {
    for (let bx = 0; bx < bw; bx++) {
      bc7Block(src, off + (by * bw + bx) * 16, px);
      for (let y = 0; y < 4 && by * 4 + y < height; y++) {
        for (let x = 0; x < 4 && bx * 4 + x < width; x++) {
          const o = ((by * 4 + y) * width + bx * 4 + x) * 4, i = (y * 4 + x) * 4;
          out[o] = px[i]; out[o + 1] = px[i + 1]; out[o + 2] = px[i + 2]; out[o + 3] = px[i + 3];
        }
      }
    }
  }
  return new ImageData(out, width, height);
}

// ---------- DDS: the header, and where one layer's mip level starts in a texture array ----------
function ddsInfo(buf) {
  const dv = new DataView(buf);
  if (buf.byteLength < 148 || dv.getUint32(0, true) !== 0x20534444) throw new Error("not a DDS file");  // "DDS "
  if (dv.getUint32(84, true) !== 0x30315844 || ![98, 99].includes(dv.getUint32(128, true))) {  // "DX10", BC7
    throw new Error("not a BC7 texture");
  }
  return { height: dv.getUint32(12, true), width: dv.getUint32(16, true), mips: Math.max(1, dv.getUint32(28, true)),
    layers: Math.max(1, dv.getUint32(140, true)), offset: 148 };
}
const bc7Bytes = (w, h) => Math.max(1, (w + 3) >> 2) * Math.max(1, (h + 3) >> 2) * 16;

// layer (0-based) at the smallest mip level still at least `size` pixels wide
function ddsLayer(buf, layer, size) {
  const d = ddsInfo(buf);
  let layerBytes = 0;
  for (let m = 0; m < d.mips; m++) layerBytes += bc7Bytes(Math.max(1, d.width >> m), Math.max(1, d.height >> m));
  let mip = 0;
  while (mip + 1 < d.mips && (d.width >> (mip + 1)) >= size) mip++;
  let off = d.offset + layer * layerBytes;
  for (let m = 0; m < mip; m++) off += bc7Bytes(Math.max(1, d.width >> m), Math.max(1, d.height >> m));
  const w = Math.max(1, d.width >> mip), h = Math.max(1, d.height >> mip);
  if (layer >= d.layers || off + bc7Bytes(w, h) > buf.byteLength) throw new Error("texture layer out of range");
  const canvas = document.createElement("canvas");
  canvas.width = w; canvas.height = h;
  canvas.getContext("2d").putImageData(decodeBC7(new Uint8Array(buf), off, w, h), 0, 0);
  return canvas;
}

// ---------- loading: each file fetched once for all the pictures wanted from it; decoded pictures kept ----------
const TREE_ART = new Map();  // "file|layer|size" -> canvas, or null when it could not be had

// wants: [{ key, file, layer (1-based, as PoB's tree data counts), size }]; calls done() after each file
async function loadTreeArt(version, wants, done) {
  const byFile = new Map();
  for (const w of wants) {
    if (!w || !w.file || TREE_ART.has(`${w.file}|${w.layer}|${w.size}`)) continue;
    byFile.set(w.file, [...(byFile.get(w.file) || []), w]);
  }
  for (const [file, list] of byFile) {
    let buf = null;
    try {
      const res = await fetch(`/api/tree/art/${encodeURIComponent(version)}/${encodeURIComponent(file)}`);
      if (res.ok) buf = await res.arrayBuffer();
    } catch (_) { /* no art: the tree is drawn on a plain background */ }
    for (const w of list) {
      const key = `${w.file}|${w.layer}|${w.size}`;
      if (TREE_ART.has(key)) continue;
      try { TREE_ART.set(key, buf ? ddsLayer(buf, w.layer - 1, w.size) : null); } catch (_) { TREE_ART.set(key, null); }
      await new Promise((r) => setTimeout(r, 0));  // let the page breathe between big pictures
    }
    buf = null;
    done();
  }
}
const treeArt = (w) => (w && w.file ? TREE_ART.get(`${w.file}|${w.layer}|${w.size}`) || null : null);
