# Test Appointments Generator

This utility helps create realistic test data for appointments (calls) in various stages of the sales process.

## Overview

The `create_test_appointments.py` script generates test data that simulates real appointments with homeowners at different stages:

1. **Booked Quote** - Appointment is scheduled but not yet assigned to a sales rep
2. **Assigned** - Appointment is assigned to a sales rep but the meeting hasn't happened yet
3. **Completed** - The sales rep has met with the homeowner, but no purchase decision yet
4. **Bought** - The homeowner has made a purchase
5. **Lost Sale** - The homeowner has decided not to purchase

## Prerequisites

- You must have a Company ID to create appointments for. You can create a test company using the `create_full_org.py` script.
- The API must be running and accessible at the BASE_URL specified in the script.

## Usage

### Basic Usage

1. Set the `COMPANY_ID` environment variable to your company's ID:

```bash
export COMPANY_ID=org_2aBcDeFgHiJkLmNoPqRsTuV
```

2. Run the script:

```bash
python create_test_appointments.py
```

This will create:
- 10 booked quotes
- 3 assigned calls
- 2 completed calls
- 3 bought calls
- 2 lost sales

### Customizing

You can modify the script to create different numbers of appointments or focus on specific stages by editing the `main()` function.

## API Details

The script uses the following endpoints:

- `/add-call` - Creates a new call record
- `/update-call-status` - Updates a call's status
- `/company/{company_id}/sales-reps` - Gets sales reps for a company

## Fields Used in Appointments

For booked quotes (the initial stage), the following fields are set:

- `company_id` - ID of the company
- `name` - Customer name (random from sample list)
- `phone_number` - Generated random phone number
- `address` - Random address from sample list
- `quote_date` - Random future date (1-14 days ahead)
- `booked` - Set to true
- `missed_call` - Set to false

For later stages, additional fields might be set depending on the stage:

- `assigned_rep_id` - For all stages beyond booked_quote
- `bought` - For bought/lost stages
- `price_if_bought` - For bought stage
- `reason_not_bought_homeowner` - For lost_sale stage

## Extending the Script

You can extend this script to:

1. Create more varied test data
2. Add additional stages
3. Create appointments with specific characteristics
4. Automate test scenario creation 