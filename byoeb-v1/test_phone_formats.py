"""
Test script to verify expert phone number format
Tests the format: 9739811075 (without 91 country code)
"""
import json

def test_phone_formats():
    """Test different phone number formats for QikChat"""
    base_number = "919739811075"
    
    formats = {
        "with_country_code": base_number,           # 919739811075
        "with_plus": f"+{base_number}",            # +919739811075  
        "without_country_code": base_number[2:],   # 9739811075
        "with_plus_91": f"+91{base_number[2:]}",   # +919739811075
    }
    
    print("📱 Phone Number Format Test")
    print("=" * 40)
    
    for format_name, number in formats.items():
        print(f"{format_name:20}: {number}")
        
        # Create a sample QikChat message payload
        sample_payload = {
            "to_contact": number,
            "type": "text",
            "text": {
                "body": "Test expert verification message"
            }
        }
        
        print(f"   Payload: {json.dumps(sample_payload, indent=6)}")
        print()
    
    print("🎯 RECOMMENDATION:")
    print("   Based on QikChat tests, use format: 9739811075")
    print("   (10 digits without country code)")

if __name__ == "__main__":
    test_phone_formats()
