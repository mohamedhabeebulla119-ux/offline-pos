# services/barcode_service.py
import os
import barcode
from barcode.writer import ImageWriter
from PIL import Image
import datetime

CODE128_PATTERNS = [
    "212222", "222122", "222221", "121223", "121322", "131222", "122213", "122312", "132212", "221213", # 0-9
    "221312", "231212", "112232", "122132", "122231", "113222", "123122", "123221", "223211", "221132", # 10-19
    "221231", "213212", "223112", "312131", "311222", "321122", "321221", "312212", "322112", "322211", # 20-29
    "212123", "212321", "232121", "111323", "131123", "131321", "112313", "132113", "132311", "211313", # 30-39
    "231113", "231311", "112133", "112331", "132131", "113123", "113321", "133121", "313121", "211331", # 40-49
    "231131", "213113", "213311", "213131", "311123", "311321", "331121", "312113", "312311", "332111", # 50-59
    "314111", "221411", "431111", "111224", "111422", "121124", "121421", "141122", "141221", "112214", # 60-69
    "112412", "122114", "122411", "142112", "142211", "241211", "221114", "413111", "241112", "134111", # 70-79
    "111242", "121142", "121241", "114212", "124112", "124211", "411212", "421112", "421211", "212141", # 80-89
    "214121", "412121", "111143", "111341", "131141", "114113", "114311", "411113", "411311", "113141", # 90-99
    "114131", "311141", "411131", "211412", "211214", "211232", "2331112" # 100-106
]

class BarcodeService:
    """
    Handles generation, existence verification, deletion, and rendering of Code 128 barcodes.
    """
    def __init__(self, folder="barcodes"):
        """Initializes the service and ensures the output folder exists."""
        self.folder = folder
        try:
            if not os.path.exists(self.folder):
                os.makedirs(self.folder)
        except Exception as e:
            print(f"Error creating barcode directory: {e}")

    def create_barcode(self, barcode_number):
        """
        Generates a Code 128 barcode image and saves it to the barcodes folder.
        
        Args:
            barcode_number (str): The barcode value to encode.
            
        Returns:
            tuple: (bool, str) -> (Success status, saved image path or error message).
        """
        try:
            # Ensure folder exists dynamically
            if not os.path.exists(self.folder):
                os.makedirs(self.folder)

            # Retrieve Code128 generator with ImageWriter for PNG format
            code128 = barcode.get('code128', str(barcode_number), writer=ImageWriter())
            
            # Save requires path without extension. It returns path with extension.
            target_path_no_ext = os.path.join(self.folder, str(barcode_number))
            actual_path = code128.save(target_path_no_ext)
            return True, actual_path
        except Exception as e:
            error_msg = f"Failed to generate barcode: {str(e)}"
            print(error_msg)
            return False, error_msg

    def barcode_exists(self, barcode_number):
        """
        Checks if the barcode PNG image file already exists.
        
        Returns:
            bool: True if exists, False otherwise.
        """
        path = self.get_barcode_path(barcode_number)
        return os.path.exists(path)

    def get_barcode_path(self, barcode_number):
        """
        Returns the expected relative file path of the barcode image.
        
        Returns:
            str: Path to the PNG image.
        """
        return os.path.join(self.folder, f"{barcode_number}.png")

    def delete_barcode(self, barcode_number):
        """
        Safely deletes the barcode PNG image from the folder.
        
        Returns:
            bool: True if deleted, False if file not found or deletion failed.
        """
        try:
            path = self.get_barcode_path(barcode_number)
            if os.path.exists(path):
                os.remove(path)
                return True
            return False
        except Exception as e:
            print(f"Error deleting barcode file: {e}")
            return False

    def generate_product_barcode(self, product_id):
        """
        Generates a standardized unique barcode identifier string.
        Format: PS000001
        
        Returns:
            str: Generated barcode string.
        """
        try:
            padded_id = str(product_id).zfill(6)
            return f"PS{padded_id}"
        except Exception as e:
            print(f"Error generating barcode value: {e}")
            return ""

    def create_barcode_for_product(self, product_id):
        """
        Generates a unique barcode identifier and creates its corresponding image.
        
        Returns:
            dict: {"barcode": generated_barcode, "image_path": barcode_path}
        """
        barcode_str = self.generate_product_barcode(product_id)
        if not barcode_str:
            return {"barcode": "", "image_path": ""}
            
        success, img_path = self.create_barcode(barcode_str)
        return {
            "barcode": barcode_str,
            "image_path": img_path if success else ""
        }

    def bulk_generate_barcodes(self, product_list):
        """
        Bulk generates barcode images for a list of product items.
        Handles attributes, dict items, and raw tuples/lists.
        
        Returns:
            dict: {"success": count, "failed": count}
        """
        summary = {"success": 0, "failed": 0}
        for item in product_list:
            barcode_val = None
            if hasattr(item, 'barcode'):
                barcode_val = item.barcode
            elif isinstance(item, dict) and 'barcode' in item:
                barcode_val = item['barcode']
            elif isinstance(item, (tuple, list)) and len(item) > 1:
                barcode_val = item[1]
                
            if barcode_val:
                success, _ = self.create_barcode(barcode_val)
                if success:
                    summary["success"] += 1
                else:
                    summary["failed"] += 1
            else:
                summary["failed"] += 1
        return summary

    # --- Backwards Compatibility Helpers ---

    @staticmethod
    def encode_code128_b(text):
        """Encodes alphanumeric text into a list of Code 128 character indices."""
        indices = [104] # Start B
        checksum = 104
        for i, char in enumerate(text):
            val = ord(char) - 32
            if val < 0 or val > 95:
                val = 0 # Space default fallback
            indices.append(val)
            checksum += val * (i + 1)
        check_digit = checksum % 103
        indices.append(check_digit)
        indices.append(106) # Stop
        return indices

    @staticmethod
    def draw_on_canvas(canvas, text, x_offset, y_offset, bar_w=2, bar_h=50, color="#ffffff"):
        """Draws barcode lines directly on a Tkinter Canvas widget."""
        indices = BarcodeService.encode_code128_b(text)
        current_x = x_offset
        canvas_objects = []
        for index in indices:
            pattern = CODE128_PATTERNS[index]
            for j, char_width in enumerate(pattern):
                w = int(char_width) * bar_w
                is_bar = (j % 2 == 0)
                if is_bar:
                    obj = canvas.create_rectangle(
                        current_x, y_offset, 
                        current_x + w, y_offset + bar_h, 
                        fill=color, outline=""
                    )
                    canvas_objects.append(obj)
                current_x += w
        mid_x = (x_offset + current_x) / 2
        text_obj = canvas.create_text(
            mid_x, y_offset + bar_h + 12, 
            text=text, fill=color, 
            font=("Courier", 10, "bold")
        )
        canvas_objects.append(text_obj)
        return canvas_objects

    @staticmethod
    def print_barcode(barcode_number):
        """Generates barcode image and opens it in default web browser for printing."""
        service = BarcodeService()
        success, filepath = service.create_barcode(barcode_number)
        if success:
            import webbrowser
            absolute_path = os.path.abspath(filepath)
            webbrowser.open(f"file:///{absolute_path}")

if __name__ == "__main__":
    service = BarcodeService(folder="barcodes_test")
    print("=== STARTING BARCODE SERVICE TEST ===")
    
    # 1. Generate sample barcode
    sample_code = "8901234567890"
    print(f"\n1. Generating Sample Barcode for '{sample_code}':")
    success, img_path = service.create_barcode(sample_code)
    print(f"   Success Status: {success}")
    
    # 2. Verify file exists
    print("\n2. Verifying File Exists:")
    exists = service.barcode_exists(sample_code)
    print(f"   Barcode Exists in Folder: {exists}")
    
    # 3. Display generated path
    print("\n3. Displaying Generated Path:")
    path = service.get_barcode_path(sample_code)
    print(f"   Expected Path: {path}")
    print(f"   Actual Path:   {img_path}")
    
    # 4. Delete barcode
    print("\n4. Deleting Barcode:")
    deleted = service.delete_barcode(sample_code)
    print(f"   Delete Status: {deleted}")
    print(f"   Still Exists?: {service.barcode_exists(sample_code)}")
    
    # 5. Generate multiple test barcodes
    print("\n5. Generating Multiple Test Barcodes:")
    mock_products = [
        {"barcode": "BULK-CODE-001"},
        {"barcode": "BULK-CODE-002"},
        {"barcode": "BULK-CODE-003"}
    ]
    summary = service.bulk_generate_barcodes(mock_products)
    print(f"   Bulk generation summary: {summary}")
    
    # Clean up test files and directories
    for p in mock_products:
        service.delete_barcode(p["barcode"])
    try:
        if os.path.exists("barcodes_test") and not os.listdir("barcodes_test"):
            os.rmdir("barcodes_test")
    except Exception as e:
        print(f"Error cleaning folder: {e}")
        
    print("\n=== BARCODE TEST RUN COMPLETED successfully ===")
