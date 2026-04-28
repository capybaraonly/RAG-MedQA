import { IModalProps } from '@/interfaces/common';
import { IFeedbackRequestBody } from '@/interfaces/request/chat';
import { zodResolver } from '@hookform/resolvers/zod';
import { useCallback } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { z } from 'zod';
import { RAG-MedQAFormItem } from './RAG-MedQA-form';
import { ButtonLoading } from './ui/button';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';
import { Form } from './ui/form';
import { Textarea } from './ui/textarea';

const FormId = 'feedback-dialog';

const FeedbackDialog = ({
  visible,
  hideModal,
  onOk,
  loading,
}: IModalProps<IFeedbackRequestBody>) => {
  const { t } = useTranslation();
  const FormSchema = z.object({
    feedback: z
      .string()
      .min(1, {
        message: t('common.namePlaceholder'),
      })
      .trim(),
  });

  const form = useForm<z.infer<typeof FormSchema>>({
    resolver: zodResolver(FormSchema),
    defaultValues: { feedback: '' },
  });

  const handleOk = useCallback(
    async (data: z.infer<typeof FormSchema>) => {
      return onOk?.({ thumbup: false, feedback: data.feedback });
    },
    [onOk],
  );

  return (
    <Dialog open={visible} onOpenChange={hideModal}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Feedback</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form
            onSubmit={form.handleSubmit(handleOk)}
            className="space-y-6"
            id={FormId}
          >
            <RAG-MedQAFormItem name="feedback">
              <Textarea> </Textarea>
            </RAG-MedQAFormItem>
          </form>
        </Form>
        <DialogFooter>
          <ButtonLoading type="submit" form={FormId} loading={loading}>
            {t('common.save')}
          </ButtonLoading>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default FeedbackDialog;
