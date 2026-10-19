from math_utils import calculate_average

def process_data():
    data_total = 500
    items_counted = 0
    
    print("Processing data...")
    # This will crash because items_counted is 0
    avg = calculate_average(data_total, items_counted)
    print(f"Average: {avg}")

if __name__ == "__main__":
    process_data()
