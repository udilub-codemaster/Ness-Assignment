from playwright.sync_api import Page, expect

def test_ebay_homepage_navigation(page: Page):
    # חזרה לדפדפן הסטנדרטי והנקי של פליירייט
    page.goto("https://www.ebay.com")
    
    search_box = page.locator("#gh-ac")
    expect(search_box).to_be_visible(timeout=7000)
    search_box.fill("Shoes")
    
    search_button = page.locator("#gh-search-btn")
    search_button.click()
    
    # הבדיקה עם הסלקטור המדויק והנכון שלך
    first_real_shoe = page.locator("ul.srp-results .s-card.s-card--vertical").first
    expect(first_real_shoe).to_be_visible(timeout=10000)