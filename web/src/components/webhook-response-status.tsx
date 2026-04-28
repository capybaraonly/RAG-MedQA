import { useTranslation } from 'react-i18next';
import { RAG-MedQAFormItem } from './RAG-MedQA-form';
import { Input } from './ui/input';

type WebHookResponseStatusFormFieldProps = {
  name: string;
};

export function WebHookResponseStatusFormField({
  name,
}: WebHookResponseStatusFormFieldProps) {
  const { t } = useTranslation();

  return (
    <RAG-MedQAFormItem name={name} label={t('flow.webhook.status')}>
      <Input type="number"></Input>
    </RAG-MedQAFormItem>
  );
}
