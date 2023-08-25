import os
import time
import sys
import json
import requests
import pandas as pd
from bs4 import BeautifulSoup

class ScrapingConstants:
    ERROR_404 = "ERROR 404 : Page/Record not found !"
    ALL_LOTS = -1

def extractTextFromHTML(html_string):
    soup = BeautifulSoup(html_string, "html.parser")
    return soup.text

def getImageUrl(json_string):
    if json_string and json_string[0] == "[":
        REPO_URL = "https://repo.siegelauctions.com/"
        json_data = json.loads(json_string[1:-1])
        return  REPO_URL + json_data["Url"]
    return json_string

def getCatalogData(catalog_values):
    if catalog_values is None:
        return None
    if catalog_values[0] == "[":
        catalog_json = json.loads(catalog_values)[0]
    return {
        "catalogNumber" : catalog_json["CatalogNumber"],
        "scottValue" : catalog_json["Value"]
    }

def getSaleData(api_endpoint):
    response = requests.get(api_endpoint)
    REPO_URL = "https://repo.siegelauctions.com/"
    if response.status_code == 200:
        response_data = response.json()
        if response_data['data'] is None:
            return None
        data = response_data["data"]["SalePublicDetail"]
        sale_data = {
            "saleNumber" : data["SaleNumber"],
            "saleName" : data["SaleName"],
            "saleDescription" : data["SaleDescription"],
            "saleStartDate" : data["SaleStartDate"],
            "saleEndDate" : data["SaleEndDate"],
            "imageURL" : REPO_URL + data["ImageURL"],
            "totalPages" : data["PageNumberMAx"],
            "saleCatalogFileUrl" : data["SaleCatalogFileUrl"],
            "saleStatusType" : data["SaleStatusType"]
        }
        if data["SaleCatalogFileUrl"] is not None:
            sale_data["SaleCatalogFileUrl"] = REPO_URL + data["SaleCatalogFileUrl"]
        return sale_data
    else:
        print("Request not successful!")

def getLotsData(api_endpoint):
    response = requests.get(api_endpoint)
    if response.status_code == 200:
        search_data = response.json()["data"]
        lots = search_data["data"]["Lot"]
        totalLotRecords = search_data["length"]["Lot"]    
        lots_data = []
        for lot in lots:
            lotNumber = lot["LotNumericalPart"]
            lotDescription = extractTextFromHTML(lot["LotDescriptionHTML"])
            lotHeadline = extractTextFromHTML(lot["HeadLine"])
            lotEstimateFrom = lot["EstimateFrom"]
            lotEstimateTo = lot["EstimateTo"]
            lotRealizedPrice = lot["Realized"]
            lotCategoryName = lot["CategoryName"]
            lotCatalogData = getCatalogData(lot["CatalogValues"])
            if lotCatalogData is None:
                lotCatalogNumber = None
                scottValue = None
            else:
                lotCatalogNumber = lotCatalogData["catalogNumber"]
                scottValue = lotCatalogData["scottValue"]
            saleStartDate = lot["SaleStartDate"]
            saleEndDate = lot["SaleEndDate"]
            saleName = lot["SaleName"]
            lotImageUrl = getImageUrl(lot["LotFile"])
            saleNumber = lot["SaleNumber"]

            lots_data.append({
                "lotNumber" : lotNumber,
                "lotDescription" : lotDescription,
                "lotHeadLine" : lotHeadline,
                "lotEstimateFrom" : lotEstimateFrom,
                "lotEstimateTo" : lotEstimateTo,
                "lotScottPrice"  : scottValue,
                "lotRealizedPrice" : lotRealizedPrice,
                "lotCategoryName" : lotCategoryName,
                "lotCatalogNumber" : lotCatalogNumber,
                "lotImageUrl" : lotImageUrl,
                "saleStartDate" : saleStartDate,
                "saleEndDate" : saleEndDate,
                "saleName" : saleName,
                "saleNumber" : saleNumber
            })
        return {
            "lotsCount": totalLotRecords,
            "data": lots_data
        }
    else:
        print("Request not successful!")

def exportToExcel(sale_data, lots_data):
    sale_df = pd.DataFrame({
        "Data": sale_data.keys(),
        "Value": sale_data.values()
    })
    lotNumbers = []
    lotDescriptions = []
    lotHeadlines = []
    lotEstimateFrom = []
    lotEstimateTo = []
    lotRealizedPrice = []
    lotCategoryNames = []
    lotCatalogNumber = []
    lotImageUrls = []
    lotScottPrices = []

    for i in range(lots_data["lotsCount"]):
        lotNumbers.append(lots_data["data"][i]["lotNumber"])
        lotDescriptions.append(lots_data["data"][i]["lotDescription"])
        lotHeadlines.append(lots_data["data"][i]["lotHeadLine"])
        lotEstimateFrom.append(lots_data["data"][i]["lotEstimateFrom"])
        lotEstimateTo.append(lots_data["data"][i]["lotEstimateTo"])
        lotRealizedPrice.append(lots_data["data"][i]["lotRealizedPrice"])
        lotScottPrices.append(lots_data["data"][i]["lotScottPrice"])
        lotCategoryNames.append(lots_data["data"][i]["lotCategoryName"])
        lotCatalogNumber.append(lots_data["data"][i]["lotCatalogNumber"])
        lotImageUrls.append(lots_data["data"][i]["lotImageUrl"])

    lots_df = pd.DataFrame({
            "lotNumber" : lotNumbers,
            "lotDescription" : lotDescriptions,
            "lotHeadLine" : lotHeadlines,      
            "lotEstimateFrom": lotEstimateFrom,
            "lotEstimateTo" : lotEstimateTo,
            "lotRealizedPrice" : lotRealizedPrice,
            "lotCategoryName" : lotCategoryNames,
            "lotCatalogNumber" : lotCatalogNumber,
            "lotImageUrl" : lotImageUrls,
            "lotScottPrice" : lotScottPrices
        })

    realized_prices_df = pd.DataFrame({
        "lotNumber" : lotNumbers,
        "realizedPrices" : lotRealizedPrice,
        "Combined Data" : [f'{lots_df["lotNumber"][i]}, {lots_df["lotRealizedPrice"][i]}' for i in range(len(lots_df))]
    })

    file_name = f"sale-{sale_data['saleNumber']}.xlsx"
    output_path = os.path.abspath(os.path.join(os.path.dirname(sys.argv[0]), "result", file_name))
    # Write the DataFrames to the new sheets
    with pd.ExcelWriter(output_path) as writer:
        sale_df.to_excel(writer, sheet_name="Sale Data", index=False)
        lots_df.to_excel(writer, sheet_name="Lots Data", index=False)
        realized_prices_df.to_excel(writer, sheet_name="Prices data", index=False)
    return output_path

def scrapeData(saleNumber, lotNumber):
    SALE_API_ENDPOINT = f"https://api.siegelauctions.com/BackOffice/SalePublicDetail/Search?SaleNumber={saleNumber}"
    sale_data = getSaleData(SALE_API_ENDPOINT)
    print("-------------------------------------------")
    if sale_data is None:
        print("No Sale data returned !")
        return 
    # print(sale_data)
    print("~ Sale url scraped!")

    if lotNumber == ScrapingConstants.ALL_LOTS:
        LOT_API_ENDPOINT = f"https://api.siegelauctions.com/BackOffice/PowerSearch/Search?SaleNumber={saleNumber}&IgnoreOtherCriteria=true&SaleDateStart=1930-01-01&Level1ID=3&AreaID=6&SubAreaID=12&CatalogTypeID=1&CatalogNumberEqualContains=1&GradeGreaterEqual=1&SortName=SaleNumber&SortOrder=false&PageIndex=0&PageSize=100000"
    else:
        LOT_API_ENDPOINT = f"https://api.siegelauctions.com/BackOffice/PowerSearch/Search?SaleNumber={saleNumber}&LotNumber={lotNumber}&IgnoreOtherCriteria=true"
    lots_data = getLotsData(LOT_API_ENDPOINT)
    if lots_data["lotsCount"] == 0:
        print("No Lots data returned !")
        return 
    # print(lots_data)
    print("~ Lots scraped!")
    output_path = exportToExcel(sale_data, lots_data)
    print(f"~ Exported the data to {output_path} !\nThis window will be automatically closed in 30 seconds. You can close this manually..")

if __name__ == "__main__":
    saleNumber = input("Enter a sale number : ")
    lotNumber = input("Enter a lot number (Press enter if you want to scrape all the lots): ")
    if lotNumber == "":
        lotNumber = ScrapingConstants.ALL_LOTS
    scrapeData(saleNumber, lotNumber)
    print("-------------------------------------------")
    time.sleep(30)