# import tabula
from selenium.webdriver import Chrome, ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import time
import os
import re
import sys

def scrape_lots(auction):
    lots_link_tag = auction.find_element(By.CSS_SELECTOR, ".cat_floater a")
    url = lots_link_tag.get_attribute("href")
    if url != "" and url not in scraped_urls:
        scraped_urls.add(url)
        options = ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--disable-javascript")
        options.add_argument("log-level=3")
        driver = Chrome(options=options)
        driver.get(url)
        actions = ActionChains(driver)
        auctionDate = driver.find_element(By.CSS_SELECTOR, ".page-title").text
        pageContents = driver.find_elements(By.CSS_SELECTOR, "#page_content > *")
        lots_data = []
        found_count = 0
        not_found_count = 0
        print(f"~ {len(driver.find_elements(By.CSS_SELECTOR, '.some-page-wrapper'))} lots found! ", end=' ')
        for child in pageContents:  
            if child.tag_name == 'a' and "cntry_href" in child.get_attribute("class").split(" "):
                cur_country = child.text
            elif child.tag_name == 'div' and 'some-page-wrapper' in child.get_attribute('class').split(" "):
                actions.move_to_element(child).perform()
                child.click()
                found_count += 1
                try:
                    image = WebDriverWait(child, 3).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".lot_image_box img")))
                    imageUrl = image.get_attribute("src")
                except Exception as e:
                    imageUrl = ""
                    not_found_count += 1
                lotNumber = child.find_element(By.CSS_SELECTOR, ".lot-column .lot_div").text
                lotCatalogNumber = child.find_element(By.CSS_SELECTOR, ".descript-column b").text.replace(cur_country, "")
                lotDescription = child.find_element(By.CSS_SELECTOR, ".descript-column .descript-div").text.replace("\x02", " ")
                lotDescription = re.sub(r'[^\x00-\x7F]+', '', lotDescription)
                estimatePrice = child.find_element(By.CSS_SELECTOR, ".price-column .descript-div").text.replace("Est. $", "").replace("+", "").replace("Cat. $", "").replace(",", "")
                lots_data.append({
                    'countryName': cur_country,
                    'lotNumber': lotNumber,
                    'lotCatalogNumber': lotCatalogNumber,
                    'lotDescription': lotDescription,
                    'estimatePrice': estimatePrice,
                    'imageUrl': imageUrl 
                })
        print("Lots scraped successfully!")
        driver.close()
        return auctionDate, lots_data
    return None, None

def has_lot_range(cell):
    lot_range_regex = r'Lot \d+ – \d+'
    matches = re.findall(lot_range_regex, cell)
    has_match = len(matches) > 0
    if not has_match:
        return False, None
    return True, matches

def parse_cell(cell):
    lot_realised_price_regex = r'Lot \d+ – Realized \$\d+[,\d+]*'
    cell = re.sub(lot_realised_price_regex, "", cell)
    data = [value.strip() for value in cell.split(".00")]
    recent_scraped_lots = []
    for value in data:
        if value.count(" ") == 1:
            prices_data[int(value.split(" ")[0])] = int(value.split(" ")[1])
            lots_present.remove(int(value.split(" ")[0]))
        elif value != "":
            problematic_cells.append(value)

def scrape_table_data(df):
    global prices_data, problematic_cells, lots_present
    prices_data = dict()
    problematic_cells = []
    lots_present = set()

    for col in df.columns:
        for i in range(len(df)):
            cell = df[col][i]
            if cell is not None and type(cell) == str:
                has_match, matches = has_lot_range(cell)
                if has_match:
                    print(f"1) {len(matches)} ranges found!, {matches}")
                    for match in matches:
                        start_lot = int(match.split(" ")[1])
                        end_lot = int(match.split(" ")[3])
                        for lot in range(start_lot, end_lot+1):
                            lots_present.add(lot)
                else:
                    parse_cell(cell)
    
    # parse problematic cells
    for cell in problematic_cells:
        compressed_cell = ''.join(cell.split(" "))
        extracted_lots = set()
        for lot in lots_present:
            if compressed_cell.startswith(str(lot)):
                prices_data[lot] = float(compressed_cell[len(str(lot)):])
                extracted_lots.add(lot)
        for lot in extracted_lots:
            lots_present.remove(lot)
    print(f"{len(prices_data.keys())} lots scraped!")
    return len(lots_present)==0, lots_present, prices_data, problematic_cells

def scrape_pdf(pdf_path):
    # print("~ Requesting for Realized prices pdf..")
    # response = requests.get(pdf_path)
    # if response.status_code == 200:
    #     print("\t~ Response received..")
    #     with open("temp-pdf.pdf", "wb") as file:
    #         file.write(response.content)
    #     print("\t~ Downloaded the pdf file! Started scraping the tables.. !")
    #     dfs = tabula.read_pdf("temp-pdf.pdf", pages='all', multiple_tables=True)
    #     print(f"\t~ {len(dfs)} tables found!")
    #     count = 1
    #     realized_prices = dict()
    #     for df in dfs:
    #         print(f"\t\t~ Scraping [{count} / {len(dfs)}] tables.. ", end='')
    #         all_lots_scraped, remaining_lots, cur_table_data, problematic_cells = scrape_table_data(df)
    #         realized_prices.update(cur_table_data)
    #         print("Done..")
    #     os.remove("temp-pdf.pdf")
    #     return realized_prices
    # else:
    #     print("~ Request failed..")
    pass

def exportToExcel(scraped_data):
    print("\n\t~ Exporting to excel --> ")
    sale_df = pd.DataFrame({
        'Data': ['saleName', 'saleNumber', 'saleCoverImage', 'saleDate'],
        'Value' : [scraped_data['saleName'], scraped_data['catalogNumber'], scraped_data['saleImageUrl'], scraped_data['saleDate']],
    })

    countries = []
    lotNumbers = []
    lotCatalogNumbers = []
    lotDescriptions = []
    lotEstimatePrices = []
    imageUrls = []
    for i in range(len(scraped_data['lots'])):
        countries.append(scraped_data['lots'][i]['countryName'])
        lotNumbers.append(scraped_data['lots'][i]['lotNumber'])
        lotCatalogNumbers.append(scraped_data['lots'][i]['lotCatalogNumber'])
        lotDescriptions.append(scraped_data['lots'][i]['lotDescription'])
        lotEstimatePrices.append(scraped_data['lots'][i]['estimatePrice'])
        imageUrls.append(scraped_data['lots'][i]['imageUrl'])
    lots_df = pd.DataFrame({
        'LotNumber' : lotNumbers,
        'CatalogNumber' : [scraped_data['catalogNumber']]*len(lotNumbers),
        'CountryName' : countries,
        'CatalogNumber' : lotCatalogNumbers,
        'LotDescriptions' : lotDescriptions,
        'LotRealizedPrice' : lotEstimatePrices,
        'ImageURL' : imageUrls
    })

    realized_prices_df = pd.DataFrame({
        'LotNumber': lots_df['LotNumber'],
        'RealizedPrice': lots_df['LotRealizedPrice'],
        'Combined Data' : [f'{lots_df["LotNumber"][i]}, {lots_df["LotRealizedPrice"][i]}' for i in range(len(lots_df))]
    })

    file_name = f"sale-{scraped_data['catalogNumber']}.xlsx"
    output_path = os.path.abspath(os.path.join(os.path.dirname(sys.argv[0]), "results", file_name))
    print(output_path)
    with pd.ExcelWriter(output_path) as writer:
        sale_df.to_excel(writer, sheet_name="Sale Data", index=False)
        lots_df.to_excel(writer, sheet_name="Lots Data", index=False)
        realized_prices_df.to_excel(writer, sheet_name="Prices Data", index=False)
    print(f"\t~ Data exported to {os.path.abspath(output_path)}\n\n")
    
    return output_path

def get_auction(driver, index):
    auctions = WebDriverWait(driver, 10).until(EC.visibility_of_all_elements_located((By.CSS_SELECTOR, ".one_third:not(.widget-area)")))
    return auctions[index]

def scrape_a_sale(auction):
    catalogNumber = auction.find_element(By.CSS_SELECTOR, ".cat_item a").get_attribute("name")
    print(f"\t~ Scraping auction {catalogNumber}", end=' ---> ')
    try:
        webview_option = auction.find_element(By.CSS_SELECTOR, "div.cat_web")
    except Exception as e:
        # print("~ERROR~ -> ",e.msg)
        print("~ Lot data not found <--")   
        return None    
    scraped_data = {
        'saleName': auction.find_element(By.CSS_SELECTOR, ".histtext:not(b)").text,
        'saleDate': auction.find_element(By.CSS_SELECTOR, ".histtext b").text,
        'saleImageUrl' : auction.find_element(By.CSS_SELECTOR, "img.alignnone").get_attribute("src"),
        'catalogNumber': catalogNumber
    } 
    if f"sale-{scraped_data['catalogNumber']}.xlsx" not in os.listdir(os.path.join(os.path.dirname(sys.argv[0]), "results")):
        print("\n\t~ Scraping lots data -> ",end='')
        auction_date, lots_data = scrape_lots(auction)
        if auction_date is not None and lots_data is not None:
            scraped_data['saleDate'] = auction_date
            scraped_data['lots'] = lots_data
            exportToExcel(scraped_data)
        else:
            print("~ Lot data not found <--")
    else:
        print(f"~ This sale data is already present in sale-{scraped_data['catalogNumber']}.xlsx")

def scrape_auctions(index=None):
    global scraped_urls
    scraped_urls = set()
    auctions = WebDriverWait(global_driver, 30).until(EC.visibility_of_all_elements_located((By.CSS_SELECTOR, ".one_third:not(.widget-area)")))
    if index is None:
        print(f"~ Scraping started -> [{len(auctions)}] auctions found !")
        for i in range(len(auctions)):
            auctions = WebDriverWait(global_driver, 10).until(EC.visibility_of_all_elements_located((By.CSS_SELECTOR, ".one_third:not(.widget-area)")))
            auction = auctions[i]
            scrape_a_sale(auction)
    else:
        auction = auctions[index]
        scrape_a_sale(auction)
        

def get_available_auctions():
    url = "https://www.easternauctions.com/public-auction-catalogs-prices-realized/"
    global auction_indices, available_auctions
    auction_indices = dict()
    print("Getting Available Sales -> Waiting to load", end=' -> ')
    global_driver.get(url)
    print("Loaded")
    auctions = WebDriverWait(global_driver, 30).until(EC.visibility_of_all_elements_located((By.CSS_SELECTOR, ".one_third:not(.widget-area)")))
    available_auctions = set()
    for i in range(len(auctions)):
        auctions = WebDriverWait(global_driver, 30).until(EC.visibility_of_all_elements_located((By.CSS_SELECTOR, ".one_third:not(.widget-area)")))
        try:
            webview_option = auctions[i].find_element(By.CSS_SELECTOR, "div.cat_web")
        except:
            continue
        catalog_number = auctions[i].find_element(By.CSS_SELECTOR, ".cat_item a").get_attribute("name")
        saleName = auctions[i].find_element(By.CSS_SELECTOR, ".histtext:not(b)").text
        available_auctions.add((catalog_number, saleName))
        auction_indices[catalog_number] = i

def line_break():
    print("- "*20)

def display_available_auctions():
    line_break()
    print("Displaying list of available sales ->")
    i = 0
    for auction in available_auctions:
        auction_name = auction[1].replace('\n', " ->")
        print(f"~ {i+1}) {auction[0]} -> {auction_name}")
        i += 1
    line_break()

def get_sale_index(sale):
    global auction_indices
    try:
        return auction_indices[sale]
    except:
        return None

if __name__ == "__main__":
    url = "https://www.easternauctions.com/public-auction-catalogs-prices-realized/"
    global available_auctions, global_driver
    options = ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-javascript")
    options.add_argument("log-level=3")
    global_driver= Chrome(options=options)
    global_driver.set_page_load_timeout(600)

    get_available_auctions()

    while True:
        try:
            line_break()
            choice = int(input("1) Scrape a sale\n2) Get available sales\n3) Quit\nEnter your choice [1-3] : "))
            if choice == 1:
                display_available_auctions()
                sale = input("\n~ Enter a sale number from above list (Press Enter to scrape all available sales): ")
                if sale == "":
                    scrape_auctions()
                elif sale not in [auction[0] for auction in available_auctions]:
                    print("Entered sale is not available on the website.\n\n")
                    continue
                else:
                    sale_index = get_sale_index(sale)
                    if not sale_index:
                        print("Sale not found!\n\n")
                        continue
                    scrape_auctions(sale_index)
            elif choice == 2:
                display_available_auctions()
            elif choice == 3:
                print("\n")
                line_break()
                print("Terminating the program ! ")
                line_break()
                time.sleep(3)
                break
        except:
            print("\nInvalid input ..")
    
