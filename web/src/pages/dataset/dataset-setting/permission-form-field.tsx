import { SelectWithSearch } from '@/components/originui/select-with-search';
import { RagMedQAFormItem } from '@/components/ragflow-form';
import { PermissionRole } from '@/constants/permission';
import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';

export function PermissionFormField() {
  const { t } = useTranslation();
  const teamOptions = useMemo(() => {
    return Object.values(PermissionRole).map((x) => ({
      label: t('knowledgeConfiguration.' + x),
      value: x,
    }));
  }, [t]);

  return (
    <RagMedQAFormItem
      name="permission"
      label={t('knowledgeConfiguration.permissions')}
      tooltip={t('knowledgeConfiguration.permissionsTip')}
      horizontal
    >
      <SelectWithSearch
        options={teamOptions}
        triggerClassName="w-full"
        testId="ds-settings-basic-permissions-select"
      ></SelectWithSearch>
    </RagMedQAFormItem>
  );
}
