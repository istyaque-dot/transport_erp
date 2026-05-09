# Docs Upload Search Update

## Change

Docs Upload tab me search ko restricted kar diya gaya hai:

- Exact GR number
- Exact truck / gadi number

Destination, date, Trip ID, file name ya remark se Docs Upload tab me search nahi hoga.

## Areas updated

- Docs Upload -> New Document Upload search
- Docs Upload -> Old/New POD-GR Download Search

## Matching rule

Spaces, hyphen aur case ignore honge.

Example:

- `UK18CA9128`
- `UK 18 CA 9128`
- `uk-18-ca-9128`

Teeno same truck number ki tarah match honge.

But partial match nahi chalega:

- Search `9128` will not match `UK18CA9128`
- Search `17` will not match `117`

