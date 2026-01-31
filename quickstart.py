"""
Quick Start Script - Test All Components
Run this from the Project directory: python quickstart.py
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test if all imports work"""
    print("\n" + "="*80)
    print("TESTING IMPORTS")
    print("="*80)

    try:
        print("\n1. Testing config import...", end=" ")
        from momentum_trader import config
        print("[OK]")

        print("2. Testing API imports...", end=" ")
        from momentum_trader.api import GammaAPI, CLOBAPI, WebSocketClient
        print("[OK]")

        print("3. Testing filter imports...", end=" ")
        from momentum_trader.filters import EventFilter
        print("[OK]")

        return True
    except Exception as e:
        print("[FAILED]")
        print(f"Error: {e}")
        return False


def test_connection():
    """Test API connection"""
    print("\n" + "="*80)
    print("TESTING API CONNECTION")
    print("="*80)

    try:
        from momentum_trader.api import GammaAPI
        from momentum_trader import config

        print("\nConnecting to Polymarket API...")
        api = GammaAPI(proxy=config.api.proxy)

        success, msg, latency = api.test_connection()

        if success:
            print(f"[OK] Connected successfully!")
            print(f"     Latency: {latency:.2f}s")
            return True
        else:
            print(f"[FAILED] Connection failed: {msg}")
            print("\nTroubleshooting:")
            print("  1. Check internet connection")
            print("  2. Try with proxy: set POLYMARKET_PROXY=http://127.0.0.1:7890")
            print("  3. Verify Polymarket API is accessible")
            return False

    except Exception as e:
        print(f"[FAILED] Error: {e}")
        return False


def test_event_filter():
    """Test event filtering"""
    print("\n" + "="*80)
    print("TESTING EVENT FILTER")
    print("="*80)

    try:
        from momentum_trader.api import GammaAPI
        from momentum_trader.filters import EventFilter
        from momentum_trader import config

        print("\nFetching live events...")
        api = GammaAPI(proxy=config.api.proxy)
        events = api.get_live_events()
        print(f"[OK] Fetched {len(events)} live events")

        if not events:
            print("[WARNING] No live events found (this is normal during off-hours)")
            return True

        print("\nFiltering events...")
        event_filter = EventFilter(api, config)
        qualified = event_filter.filter_and_score_events(events)
        print(f"[OK] Qualified: {len(qualified)}/{len(events)} events")

        if qualified:
            print("\nTop 3 events:")
            for i, score in enumerate(qualified[:3], 1):
                print(f"  {i}. {score.title[:60]} (Score: {score.total_score:.1f})")

        return True

    except Exception as e:
        print(f"[FAILED] Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def show_menu():
    """Show main menu"""
    print("\n" + "="*80)
    print("QUICK START MENU")
    print("="*80)
    print("\nWhat would you like to do?\n")
    print("1. Run Event Filter Demo (recommended first)")
    print("2. Run Real-time Data Collector (headless)")
    print("3. Show How to Run Dashboard (visual)")
    print("4. Run All Tests Again")
    print("5. Show Documentation")
    print("6. Exit")
    print("\n" + "="*80)

    choice = input("\nEnter choice (1-6): ").strip()
    return choice


def run_demo():
    """Run event filter demo"""
    print("\n" + "="*80)
    print("RUNNING EVENT FILTER DEMO")
    print("="*80 + "\n")

    try:
        # Import the example directly
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "event_filter_demo",
            "momentum_trader/examples/event_filter_demo.py"
        )
        demo_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(demo_module)
        demo_module.main()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


def run_collector():
    """Run real-time collector"""
    print("\n" + "="*80)
    print("STARTING REAL-TIME DATA COLLECTOR")
    print("="*80)
    print("\nThis will collect data continuously.")
    print("Press Ctrl+C to stop.\n")

    import time
    time.sleep(2)

    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "realtime_collector",
            "momentum_trader/data/realtime_collector.py"
        )
        collector_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(collector_module)

        import asyncio
        asyncio.run(collector_module.main())
    except KeyboardInterrupt:
        print("\n\nStopped by user.")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


def show_dashboard_instructions():
    """Show how to run dashboard"""
    print("\n" + "="*80)
    print("HOW TO RUN THE DASHBOARD")
    print("="*80)
    print("\nThe dashboard is a Streamlit web application.")
    print("\nOption 1: Run from command line")
    print("-" * 40)
    print("  streamlit run momentum_trader\\dashboard\\realtime_dashboard.py")
    print("\nOption 2: Use Python directly")
    print("-" * 40)
    print("  python -m streamlit run momentum_trader\\dashboard\\realtime_dashboard.py")
    print("\nOption 3: If streamlit not installed")
    print("-" * 40)
    print("  pip install streamlit")
    print("  then run the command from Option 1")
    print("\n" + "="*80)


def show_docs():
    """Show documentation links"""
    print("\n" + "="*80)
    print("DOCUMENTATION")
    print("="*80)
    print("\nAvailable Documentation:\n")
    print("1. QUICKSTART.md         - Get started in 5 minutes")
    print("2. REALTIME_SUMMARY.md   - Real-time system overview")
    print("3. STRATEGY_ANALYSIS.md  - Honest strategy analysis (READ THIS!)")
    print("4. momentum_trader/README.md - Technical documentation")
    print("\nKey Components:\n")
    print("- momentum_trader/api/          - API clients")
    print("- momentum_trader/filters/      - Event filtering")
    print("- momentum_trader/data/         - Data collection")
    print("- momentum_trader/dashboard/    - Real-time dashboard")
    print("- momentum_trader/examples/     - Example scripts")
    print("\nQuick Commands:\n")
    print("  python run_collector.py    - Run data collector")
    print("  streamlit run momentum_trader\\dashboard\\realtime_dashboard.py")
    print("\n" + "="*80)


def main():
    """Main function"""
    print("\n" + "="*80)
    print("POLYMARKET MOMENTUM TRADER - QUICK START")
    print("="*80)
    print("\nThis script will test all components and help you get started.\n")

    # Run tests
    if not test_imports():
        print("\n[FAILED] Import test failed. Please check your installation.")
        return 1

    if not test_connection():
        print("\n[WARNING] Connection test failed. Check troubleshooting steps above.")
        response = input("\nContinue anyway? (y/n): ").strip().lower()
        if response != 'y':
            return 1

    if not test_event_filter():
        print("\n[WARNING] Event filter test had issues.")
        response = input("\nContinue anyway? (y/n): ").strip().lower()
        if response != 'y':
            return 1

    print("\n[OK] All tests passed!\n")

    # Main menu loop
    while True:
        choice = show_menu()

        if choice == '1':
            run_demo()
            input("\nPress Enter to continue...")
        elif choice == '2':
            run_collector()
            input("\nPress Enter to continue...")
        elif choice == '3':
            show_dashboard_instructions()
            input("\nPress Enter to continue...")
        elif choice == '4':
            test_imports()
            test_connection()
            test_event_filter()
            input("\nPress Enter to continue...")
        elif choice == '5':
            show_docs()
            input("\nPress Enter to continue...")
        elif choice == '6':
            print("\nGoodbye!\n")
            break
        else:
            print("\n[ERROR] Invalid choice. Please enter 1-6.")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
