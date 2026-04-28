import { useTranslation } from 'react-i18next';
import { RagMedQAFormItem } from './ragflow-form';
import { Input } from './ui/input';

type WebHookResponseStatusFormFieldProps = {
  name: string;
};

export function WebHookResponseStatusFormField({
  name,
}: WebHookResponseStatusFormFieldProps) {
  const { t } = useTranslation();

  return (
    <RagMedQAFormItem name={name} label={t('flow.webhook.status')}>
      <Input type="number"></Input>
    </RagMedQAFormItem>
  );
}
