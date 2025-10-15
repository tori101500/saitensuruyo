from PIL import Image
import pytesseract

def extract_text_from_image(image_path):
    img = Image.open(image_path)
    text = pytesseract.image_to_string(img, lang='jpn')
    return text

def main():
    image_path = input("画像ファイルのパスを入力してください: ")
    extracted_text = extract_text_from_image(image_path)
    print("\n--- 抽出されたテキスト ---\n")
    print(extracted_text)
    print("\n------------------------\n")

if __name__ == "__main__":
    main()