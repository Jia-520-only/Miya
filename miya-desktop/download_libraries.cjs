// pixi-live2d-display 下载脚本
const https = require('https');
const fs = require('fs');
const path = require('path');

const downloads = [
  {
    url: 'https://cdn.jsdelivr.net/npm/pixi.js@6.5.10/dist/pixi.min.js',
    filename: 'pixi.min.js'
  },
  {
    url: 'https://cdn.jsdelivr.net/npm/pixi-live2d-display@0.4.0/dist/index.min.js',
    filename: 'pixi-live2d-display.min.js'
  }
];

const downloadFile = (url, filename) => {
  return new Promise((resolve, reject) => {
    console.log(`正在下载: ${filename}`);

    const file = fs.createWriteStream(filename);

    https.get(url, (response) => {
      if (response.statusCode === 302 || response.statusCode === 301) {
        // 重定向
        https.get(response.headers.location, (res) => {
          res.pipe(file);
          file.on('finish', () => {
            file.close();
            console.log(`✓ ${filename} 下载完成`);
            resolve();
          });
        }).on('error', (err) => {
          fs.unlink(filename, () => {});
          reject(err);
        });
      } else {
        response.pipe(file);
        file.on('finish', () => {
          file.close();
          console.log(`✓ ${filename} 下载完成`);
          resolve();
        });
      }
    }).on('error', (err) => {
      fs.unlink(filename, () => {});
      reject(err);
    });
  });
};

async function main() {
  const librariesDir = path.join(__dirname, 'public', 'libraries');

  // 确保目录存在
  if (!fs.existsSync(librariesDir)) {
    fs.mkdirSync(librariesDir, { recursive: true });
    console.log(`创建目录: ${librariesDir}`);
  }

  try {
    console.log('开始下载 Live2D 所需库文件...\n');
    for (const download of downloads) {
      const filepath = path.join(librariesDir, download.filename);
      await downloadFile(download.url, filepath);
    }
    console.log('\n所有库文件下载完成！');
  } catch (error) {
    console.error('\n下载失败:', error.message);
    process.exit(1);
  }
}

main();
