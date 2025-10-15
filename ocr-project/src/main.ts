import { OCR } from './ocr/ocr';

const main = async () => {
    const ocr = new OCR();
    const imagePath = 'path/to/image.png'; // 画像のパスを指定
    const textResult = await ocr.extractText(imagePath);
    console.log('抽出されたテキスト:', textResult);
};

main().catch(error => {
    console.error('エラーが発生しました:', error);
});