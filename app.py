from PIL import Image
import pytesseract

def extract_text(image_path: str) -> str:
    """画像からテキストを抽出する"""
    try:
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img, lang='jpn')
        return text.strip()
    except Exception as e:
        return f"エラー: {e}"

def main():
    print("=== OCRテキスト抽出アプリ ===")
    image_path = input("画像ファイルのパスを入力してください: ").strip()
    result = extract_text(image_path)
    print("\n--- 抽出結果 ---\n")
    print(result)
    print("\n----------------\n")

if __name__ == "__main__":
    main()