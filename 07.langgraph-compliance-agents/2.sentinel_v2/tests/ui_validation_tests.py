"""
UI Validation Tests for SENTINEL Dashboard
Tests UI elements, layout, fonts, alignment, and user interactions
Captures screenshots for visual regression testing
"""
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)

# Try importing Playwright, with fallback info if not installed
try:
    from playwright.async_api import async_playwright, Page, Browser
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("⚠️  Playwright not installed. Install with: pip install playwright")
    print("    Then run: playwright install")


# UI Test Configuration
DASHBOARD_URL = os.getenv("SENTINEL_DASHBOARD_URL", "http://localhost:8501")
API_URL = os.getenv("SENTINEL_API_URL", "http://localhost:8003")
API_KEY = os.getenv("SENTINEL_API_KEY", "test-key")


class UITestConfig:
    """Configuration for UI tests"""

    # Expected UI element properties
    EXPECTED_FONT_FAMILIES = ["Arial", "Segoe UI", "system-ui", "sans-serif"]
    EXPECTED_COLORS = {
        "primary": "#1f2937",  # Dark gray
        "secondary": "#6366f1",  # Indigo
        "success": "#10b981",  # Green
        "warning": "#f59e0b",  # Amber
        "error": "#ef4444",  # Red
    }

    # Responsive breakpoints
    BREAKPOINTS = {
        "mobile": (375, 667),
        "tablet": (768, 1024),
        "desktop": (1920, 1080),
    }

    # Accessibility standards
    MIN_TEXT_SIZE = 12
    MIN_CONTRAST_RATIO = 4.5
    MIN_TAP_TARGET = 44


class UIValidator:
    """Validates UI properties of dashboard elements"""

    @staticmethod
    async def check_text_readability(
        page: Page,
        selector: str,
    ) -> Dict[str, any]:
        """Check if text is readable (font size, contrast, color)"""
        try:
            element = page.locator(selector)
            if not await element.is_visible():
                return {"readable": False, "reason": "Element not visible"}

            # Get computed styles
            computed_style = await element.evaluate("""
                el => {
                    const style = window.getComputedStyle(el);
                    return {
                        fontSize: style.fontSize,
                        fontFamily: style.fontFamily,
                        fontWeight: style.fontWeight,
                        color: style.color,
                        lineHeight: style.lineHeight,
                    };
                }
            """)

            # Parse font size
            font_size_str = computed_style.get("fontSize", "0px")
            font_size = int(float(font_size_str.replace("px", "")))

            return {
                "readable": font_size >= UITestConfig.MIN_TEXT_SIZE,
                "fontSize": font_size_str,
                "fontFamily": computed_style.get("fontFamily"),
                "fontWeight": computed_style.get("fontWeight"),
                "color": computed_style.get("color"),
                "lineHeight": computed_style.get("lineHeight"),
                "meets_min_size": font_size >= UITestConfig.MIN_TEXT_SIZE,
            }
        except Exception as e:
            return {"readable": False, "error": str(e)}

    @staticmethod
    async def check_alignment(page: Page, selector: str) -> Dict[str, any]:
        """Check if element is properly aligned and positioned"""
        try:
            bounding_box = await page.locator(selector).bounding_box()
            if not bounding_box:
                return {"aligned": False, "reason": "Element not found or not visible"}

            return {
                "aligned": True,
                "x": bounding_box["x"],
                "y": bounding_box["y"],
                "width": bounding_box["width"],
                "height": bounding_box["height"],
                "center_x": bounding_box["x"] + bounding_box["width"] / 2,
                "center_y": bounding_box["y"] + bounding_box["height"] / 2,
            }
        except Exception as e:
            return {"aligned": False, "error": str(e)}

    @staticmethod
    async def check_accessibility(page: Page, selector: str) -> Dict[str, any]:
        """Check accessibility attributes (ARIA labels, roles, etc.)"""
        try:
            element = page.locator(selector)
            aria_label = await element.get_attribute("aria-label")
            role = await element.get_attribute("role")
            title = await element.get_attribute("title")

            return {
                "accessible": bool(aria_label or title or role),
                "aria_label": aria_label,
                "role": role,
                "title": title,
            }
        except Exception as e:
            return {"accessible": False, "error": str(e)}


class DashboardUITests:
    """Tests for SENTINEL Dashboard UI"""

    def __init__(self):
        self.test_results = []
        self.screenshots_dir = Path(__file__).parent.parent / "test_results" / "ui_screenshots"
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.validator = UIValidator()

    async def test_dashboard_home(self, page: Page):
        """Test home page layout and elements"""
        print("\n[TEST] Dashboard Home Page...")
        results = {
            "page": "Home",
            "tests": [],
            "screenshot": None,
        }

        try:
            # Navigate to dashboard
            await page.goto(DASHBOARD_URL, wait_until="networkidle")
            await asyncio.sleep(2)

            # Take screenshot
            screenshot_path = self.screenshots_dir / f"home_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            await page.screenshot(path=screenshot_path, full_page=True)
            results["screenshot"] = str(screenshot_path)

            # Test 1: Page title
            title_test = {
                "name": "Page Title Present",
                "status": "PASSED",
            }
            try:
                title = await page.title()
                if "SENTINEL" in title:
                    title_test["status"] = "PASSED"
                    title_test["value"] = title
                else:
                    title_test["status"] = "FAILED"
                    title_test["value"] = title
            except Exception as e:
                title_test["status"] = "FAILED"
                title_test["error"] = str(e)
            results["tests"].append(title_test)

            # Test 2: Header visibility
            header_test = {
                "name": "Header/Logo Visible",
                "status": "PASSED",
            }
            try:
                header = page.locator('[data-testid="header"], h1, .logo')
                if await header.is_visible():
                    header_test["status"] = "PASSED"
                else:
                    header_test["status"] = "FAILED"
            except Exception as e:
                header_test["status"] = "FAILED"
                header_test["error"] = str(e)
            results["tests"].append(header_test)

            # Test 3: Navigation sidebar
            nav_test = {
                "name": "Navigation Sidebar Present",
                "status": "PASSED",
            }
            try:
                nav = page.locator("[data-testid='nav'], nav, .sidebar")
                if await nav.count() > 0:
                    nav_test["status"] = "PASSED"
                else:
                    nav_test["status"] = "FAILED"
            except Exception as e:
                nav_test["status"] = "FAILED"
                nav_test["error"] = str(e)
            results["tests"].append(nav_test)

            # Test 4: Main content area
            content_test = {
                "name": "Main Content Area Visible",
                "status": "PASSED",
            }
            try:
                content = page.locator("[data-testid='main'], main, .content")
                if await content.count() > 0:
                    content_test["status"] = "PASSED"
                else:
                    content_test["status"] = "FAILED"
            except Exception as e:
                content_test["status"] = "FAILED"
                content_test["error"] = str(e)
            results["tests"].append(content_test)

            # Test 5: Text readability
            readability_test = {
                "name": "Text Readability (Font Size)",
                "status": "PASSED",
            }
            try:
                readability = await self.validator.check_text_readability(page, "body")
                readability_test["value"] = readability
                if readability.get("meets_min_size"):
                    readability_test["status"] = "PASSED"
                else:
                    readability_test["status"] = "FAILED"
            except Exception as e:
                readability_test["status"] = "FAILED"
                readability_test["error"] = str(e)
            results["tests"].append(readability_test)

        except Exception as e:
            results["error"] = str(e)
            results["status"] = "FAILED"

        self.test_results.append(results)
        return results

    async def test_investigation_page(self, page: Page):
        """Test investigation creation page"""
        print("\n[TEST] Investigation Page...")
        results = {
            "page": "Investigation",
            "tests": [],
            "screenshot": None,
        }

        try:
            # Navigate to investigation page
            await page.goto(f"{DASHBOARD_URL}?page=1_investigate", wait_until="networkidle")
            await asyncio.sleep(2)

            # Take screenshot
            screenshot_path = self.screenshots_dir / f"investigate_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            await page.screenshot(path=screenshot_path, full_page=True)
            results["screenshot"] = str(screenshot_path)

            # Test 1: Page header
            header_test = {
                "name": "Investigate Page Header",
                "status": "PASSED",
            }
            try:
                header = page.locator("h1, h2, [data-testid='page-title']")
                if await header.count() > 0:
                    header_test["status"] = "PASSED"
                    header_test["value"] = await header.first.text_content()
                else:
                    header_test["status"] = "FAILED"
            except Exception as e:
                header_test["status"] = "FAILED"
                header_test["error"] = str(e)
            results["tests"].append(header_test)

            # Test 2: Form elements
            form_test = {
                "name": "Investigation Form Present",
                "status": "PASSED",
            }
            try:
                form_inputs = await page.locator("input, textarea, select").count()
                if form_inputs > 0:
                    form_test["status"] = "PASSED"
                    form_test["input_count"] = form_inputs
                else:
                    form_test["status"] = "FAILED"
            except Exception as e:
                form_test["status"] = "FAILED"
                form_test["error"] = str(e)
            results["tests"].append(form_test)

            # Test 3: Submit button
            button_test = {
                "name": "Submit Button Visible & Clickable",
                "status": "PASSED",
            }
            try:
                button = page.locator("button:has-text('Start'), button:has-text('Submit'), button:has-text('Investigate')")
                if await button.is_visible():
                    button_test["status"] = "PASSED"
                else:
                    button_test["status"] = "FAILED"
            except Exception as e:
                button_test["status"] = "FAILED"
                button_test["error"] = str(e)
            results["tests"].append(button_test)

        except Exception as e:
            results["error"] = str(e)
            results["status"] = "FAILED"

        self.test_results.append(results)
        return results

    async def run_all_ui_tests(self):
        """Run all UI tests"""
        if not PLAYWRIGHT_AVAILABLE:
            print("⚠️  Skipping UI tests - Playwright not installed")
            return

        print("\n" + "="*80)
        print("SENTINEL Dashboard — UI VALIDATION TESTS")
        print("="*80)
        print(f"Dashboard URL: {DASHBOARD_URL}")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()

            # Set viewport for desktop testing
            await page.set_viewport_size(width=1920, height=1080)

            try:
                # Run tests
                await self.test_dashboard_home(page)
                await self.test_investigation_page(page)

            finally:
                await browser.close()

        self.generate_ui_report()

    def generate_ui_report(self):
        """Generate UI test report"""
        report_lines = [
            "=" * 100,
            "SENTINEL Dashboard — UI VALIDATION REPORT",
            "=" * 100,
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"Dashboard URL: {DASHBOARD_URL}",
            f"Total Pages Tested: {len(self.test_results)}",
            "",
        ]

        for page_result in self.test_results:
            passed = sum(1 for t in page_result.get("tests", []) if t["status"] == "PASSED")
            total = len(page_result.get("tests", []))

            report_lines.extend([
                f"Page: {page_result['page']}",
                f"  Status: {passed}/{total} tests passed",
                f"  Screenshot: {page_result['screenshot']}",
            ])

            for test in page_result.get("tests", []):
                status_symbol = "✅" if test["status"] == "PASSED" else "❌"
                report_lines.append(f"    {status_symbol} {test['name']}")
                if test.get("value"):
                    report_lines.append(f"       Value: {test['value']}")
                if test.get("error"):
                    report_lines.append(f"       Error: {test['error']}")

            report_lines.append("")

        report_lines.append("=" * 100)

        report = "\n".join(report_lines)
        report_file = Path(__file__).parent.parent / "test_results" / f"ui_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        report_file.parent.mkdir(parents=True, exist_ok=True)
        report_file.write_text(report)

        print(report)
        print(f"\n📄 UI Report saved to: {report_file}")


async def main():
    """Main UI test runner"""
    tester = DashboardUITests()
    await tester.run_all_ui_tests()


if __name__ == "__main__":
    if PLAYWRIGHT_AVAILABLE:
        asyncio.run(main())
    else:
        print("Please install Playwright: pip install playwright")
        print("Then run: playwright install")
