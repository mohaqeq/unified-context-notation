# Show how many categories are below a category

The storefront navigation wants to know whether a category has any sub-categories, and how many, without paging through `children`. Please add a non-null `descendantsCount: Int!` field to the `Category` type: the number of categories below it at all levels (children, grandchildren and so on), not counting the category itself. A category without sub-categories returns `0`. The field is public like the rest of the category data.
