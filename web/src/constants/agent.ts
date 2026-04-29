export enum AgentCategory {
  All = 'all',
  Published = 'published',
}
export enum AgentQuery {
  Category = 'category',
}
export enum SwitchLogicOperator {
  And = 'and',
  Or = 'or',
}
export enum ComparisonOperator {
  Equal = 'equal',
  NotEqual = 'not_equal',
  Contains = 'contains',
}
export const SwitchOperatorOptions: { label: string; value: string }[] = [];
