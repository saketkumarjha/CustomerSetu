#!/usr/bin/env python3
"""
Quick test script to verify OpenAI API key is valid and has access to GPT-4o.
Run this before starting the backend to ensure agents will work.

Usage:
    cd backend
    python test_openai_key.py
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_openai_connection():
    """Test OpenAI API key and model access."""
    
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        print("❌ ERROR: OPENAI_API_KEY not found in .env file")
        print("\nPlease add your OpenAI API key to backend/.env:")
        print("OPENAI_API_KEY=sk-proj-YOUR-KEY-HERE")
        return False
    
    if api_key == "your-valid-openai-api-key-here":
        print("❌ ERROR: OPENAI_API_KEY is still the placeholder value")
        print("\nPlease replace it with your actual OpenAI API key from:")
        print("https://platform.openai.com/api-keys")
        return False
    
    print(f"✓ Found API key: {api_key[:20]}...{api_key[-4:]}")
    print("\nTesting OpenAI API connection...")
    
    try:
        from openai import OpenAI
        
        client = OpenAI(api_key=api_key, timeout=30.0)
        
        # Test basic connection
        print("  → Testing authentication...")
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say 'OK' if you can read this."}
            ],
            max_tokens=10,
            temperature=0.1
        )
        
        result = response.choices[0].message.content
        print(f"  → Response: {result}")
        
        # Test JSON mode (used by fanout agents)
        print("  → Testing JSON mode...")
        json_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Respond with JSON only."},
                {"role": "user", "content": "Return a JSON object with a 'status' field set to 'ok'."}
            ],
            response_format={"type": "json_object"},
            max_tokens=20,
            temperature=0.1
        )
        
        json_result = json_response.choices[0].message.content
        print(f"  → JSON Response: {json_result}")
        
        print("\n✅ SUCCESS: OpenAI API key is valid and GPT-4o is accessible!")
        print("\nYour agents should work correctly now.")
        print("You can start the backend server with:")
        print("  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
        
        return True
        
    except ImportError:
        print("❌ ERROR: openai package not installed")
        print("\nInstall it with:")
        print("  pip install openai")
        return False
        
    except Exception as e:
        error_msg = str(e)
        print(f"\n❌ ERROR: {error_msg}")
        
        if "authentication" in error_msg.lower() or "401" in error_msg:
            print("\n🔑 Authentication Error:")
            print("  - Your API key is invalid or expired")
            print("  - Get a new key from: https://platform.openai.com/api-keys")
            
        elif "rate_limit" in error_msg.lower() or "429" in error_msg:
            print("\n⏱️  Rate Limit Error:")
            print("  - You've exceeded your API rate limit")
            print("  - Wait a few minutes and try again")
            print("  - Check your usage: https://platform.openai.com/usage")
            
        elif "insufficient_quota" in error_msg.lower() or "quota" in error_msg.lower():
            print("\n💳 Quota Error:")
            print("  - Your OpenAI account has no credits")
            print("  - Add billing: https://platform.openai.com/account/billing")
            
        elif "model" in error_msg.lower() and "not found" in error_msg.lower():
            print("\n🚫 Model Access Error:")
            print("  - Your API key doesn't have access to GPT-4o")
            print("  - You may need to upgrade your OpenAI tier")
            print("  - Or use gpt-3.5-turbo instead (update fanout_agents.py)")
            
        else:
            print("\n🌐 Connection Error:")
            print("  - Check your internet connection")
            print("  - Verify OpenAI service status: https://status.openai.com/")
            print("  - Check if you're behind a proxy/firewall")
        
        return False


if __name__ == "__main__":
    success = test_openai_connection()
    sys.exit(0 if success else 1)
