"""
Test script for Gemini image generation with text + image input.
This tests if your API key supports image generation.
"""

from google import genai
from PIL import Image
import os

# Your API key
GEMINI_API_KEY = 'AIzaSyB961o81sr_ZYe7TDdzYoSpbiZnmnc2Tx0'

def test_image_generation():
    print("=" * 50)
    print("Testing Gemini Image Generation")
    print("=" * 50)
    
    # Get the template image
    script_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(script_dir, "quiz_template.png")
    
    if not os.path.exists(template_path):
        print(f"ERROR: Template image not found at {template_path}")
        return
    
    print(f"✓ Template image found: {template_path}")
    
    # Load the image
    template_image = Image.open(template_path)
    print(f"✓ Image loaded: {template_image.size}")
    
    # Create client
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        print("✓ Gemini client created")
    except Exception as e:
        print(f"✗ Failed to create client: {e}")
        return
    
    # Test prompt
    prompt = """
    Create a quiz challenge image in EXACTLY the same style and format as the reference image I'm providing.
    
    Keep the same:
    - Dark background color
    - Title style at the top with "Python Challenge"
    - Code box layout with dark background
    - Answer options A, B, C, D with colored labels on the left
    - Same font styles and colors
    
    But change the content to:
    - Title: "Python Challenge"
    - Question: What is the output of print(2**3)?
    - Code block: print(2**3)
    - Options:
    A) 6
    B) 8
    C) 9
    D) Error
    
    Generate only the image.
    """
    
    print("\nAttempting image generation...")
    print(f"Using model: gemini-2.5-flash-image")
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=[prompt, template_image],
        )
        
        print(f"\n✓ Got response!")
        print(f"Response type: {type(response)}")
        
        # Check for parts
        if hasattr(response, 'parts'):
            print(f"Number of parts: {len(response.parts)}")
            
            for i, part in enumerate(response.parts):
                print(f"\nPart {i}:")
                if hasattr(part, 'text') and part.text:
                    print(f"  - Text: {part.text[:200]}...")
                if hasattr(part, 'inline_data') and part.inline_data:
                    print(f"  - Has inline_data (image)!")
                    # Try to save the image
                    try:
                        generated_image = part.as_image()
                        output_path = os.path.join(script_dir, "test_generated.png")
                        generated_image.save(output_path)
                        print(f"  ✓ Image saved to: {output_path}")
                    except Exception as save_err:
                        print(f"  ✗ Failed to save image: {save_err}")
        else:
            print(f"Response text: {response.text[:500] if hasattr(response, 'text') else 'No text'}")
            
    except Exception as e:
        print(f"\n✗ Generation failed: {e}")
        print(f"Error type: {type(e).__name__}")
        
        # Additional debug
        import traceback
        traceback.print_exc()

def test_simple_generation():
    """Test basic text-to-image without reference."""
    print("\n" + "=" * 50)
    print("Testing Simple Text-to-Image (No reference)")
    print("=" * 50)
    
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents="Generate a simple blue square image with the text 'TEST' in white.",
        )
        
        print(f"✓ Got response!")
        
        if hasattr(response, 'parts'):
            for part in response.parts:
                if hasattr(part, 'inline_data') and part.inline_data:
                    print("✓ Image generated successfully!")
                    generated_image = part.as_image()
                    generated_image.save("test_simple.png")
                    print("✓ Saved to test_simple.png")
                    return
                elif hasattr(part, 'text') and part.text:
                    print(f"Text response: {part.text[:300]}")
        
        print("✗ No image in response")
        
    except Exception as e:
        print(f"✗ Failed: {e}")
        import traceback
        traceback.print_exc()

def list_available_models():
    """List models to see what's available."""
    print("\n" + "=" * 50)
    print("Checking Available Models")
    print("=" * 50)
    
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        # List models
        models = client.models.list()
        print("Available models:")
        for model in models:
            if 'image' in str(model).lower() or 'imagen' in str(model).lower() or 'flash' in str(model).lower():
                print(f"  - {model}")
                
    except Exception as e:
        print(f"✗ Failed to list models: {e}")

if __name__ == "__main__":
    list_available_models()
    test_simple_generation()
    test_image_generation()
    
    print("\n" + "=" * 50)
    print("Test Complete!")
    print("=" * 50)
