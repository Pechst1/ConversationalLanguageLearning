import React from 'react';
import { ActivityIndicator, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { useForm, Controller } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import * as yup from 'yup';
import { useLearnerProfileSetup } from '../../services/api/auth';

const goalsOptions = ['Travel', 'Career', 'Exam preparation', 'Daily conversation', 'Culture'];

interface LearnerProfileForm {
  level: string;
  customGoal?: string;
  goals: string[];
}

const profileSchema = yup
  .object({
    level: yup.string().required('Select your level'),
    goals: yup.array(yup.string()).min(1, 'Choose at least one goal'),
    customGoal: yup.string().optional(),
  })
  .required();

type LearnerProfileSetupScreenProps = {
  onSuccess: () => void;
};

export const LearnerProfileSetupScreen: React.FC<LearnerProfileSetupScreenProps> = ({ onSuccess }) => {
  const { control, handleSubmit, watch, setValue, formState } = useForm<LearnerProfileForm>({
    resolver: yupResolver(profileSchema),
    defaultValues: { level: '', goals: [] },
  });
  const profileMutation = useLearnerProfileSetup();
  const selectedGoals = watch('goals');

  const toggleGoal = (goal: string) => {
    const isSelected = selectedGoals.includes(goal);
    const nextGoals = isSelected ? selectedGoals.filter((item) => item !== goal) : [...selectedGoals, goal];
    setValue('goals', nextGoals, { shouldValidate: true });
  };

  const onSubmit = handleSubmit(async ({ customGoal, goals, level }) => {
    const payloadGoals = customGoal ? Array.from(new Set([...goals, customGoal])) : goals;
    await profileMutation.mutateAsync({ level, goals: payloadGoals });
    onSuccess();
  });

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Tell us about your learning</Text>
      <Controller
        control={control}
        name="level"
        render={({ field: { onChange, onBlur, value } }) => (
          <View style={styles.fieldContainer}>
            <Text style={styles.label}>Current level</Text>
            <TextInput
              accessibilityLabel="level-input"
              placeholder="e.g. Beginner"
              style={styles.input}
              onBlur={onBlur}
              onChangeText={onChange}
              value={value}
            />
            {formState.errors.level && <Text style={styles.error}>{formState.errors.level.message}</Text>}
          </View>
        )}
      />

      <View style={styles.fieldContainer}>
        <Text style={styles.label}>Learning goals</Text>
        {goalsOptions.map((goal) => {
          const isSelected = selectedGoals.includes(goal);
          return (
            <TouchableOpacity
              key={goal}
              accessibilityRole="checkbox"
              accessibilityState={{ checked: isSelected }}
              style={[styles.goalChip, isSelected && styles.goalChipSelected]}
              onPress={() => toggleGoal(goal)}
            >
              <Text style={[styles.goalChipLabel, isSelected && styles.goalChipLabelSelected]}>{goal}</Text>
            </TouchableOpacity>
          );
        })}
        {formState.errors.goals && <Text style={styles.error}>{formState.errors.goals.message as string}</Text>}
      </View>

      <Controller
        control={control}
        name="customGoal"
        render={({ field: { onChange, onBlur, value } }) => (
          <View style={styles.fieldContainer}>
            <Text style={styles.label}>Custom goal (optional)</Text>
            <TextInput
              accessibilityLabel="custom-goal-input"
              placeholder="What else do you want to achieve?"
              style={styles.input}
              onBlur={onBlur}
              onChangeText={onChange}
              value={value}
            />
          </View>
        )}
      />

      {profileMutation.isError && (
        <Text style={styles.error}>Saving your profile failed. Please try again.</Text>
      )}

      <TouchableOpacity
        accessibilityRole="button"
        onPress={onSubmit}
        style={[styles.primaryButton, profileMutation.isLoading && styles.disabledButton]}
        disabled={profileMutation.isLoading}
      >
        {profileMutation.isLoading ? (
          <ActivityIndicator color="#ffffff" />
        ) : (
          <Text style={styles.primaryButtonLabel}>Continue</Text>
        )}
      </TouchableOpacity>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 24,
    backgroundColor: '#ffffff',
  },
  title: {
    fontSize: 28,
    fontWeight: '700',
    marginBottom: 24,
  },
  fieldContainer: {
    marginBottom: 16,
  },
  label: {
    fontSize: 14,
    color: '#4f4f4f',
    marginBottom: 6,
  },
  input: {
    borderWidth: 1,
    borderColor: '#d0d0d0',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 16,
  },
  goalChip: {
    paddingVertical: 10,
    paddingHorizontal: 16,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: '#d0d0d0',
    alignSelf: 'flex-start',
    marginRight: 8,
    marginBottom: 8,
  },
  goalChipSelected: {
    backgroundColor: '#0066ff',
    borderColor: '#0066ff',
  },
  goalChipLabel: {
    color: '#4f4f4f',
  },
  goalChipLabelSelected: {
    color: '#ffffff',
    fontWeight: '600',
  },
  error: {
    color: '#d42c2c',
    marginTop: 4,
  },
  primaryButton: {
    backgroundColor: '#0066ff',
    paddingVertical: 14,
    borderRadius: 8,
    alignItems: 'center',
    marginTop: 8,
  },
  disabledButton: {
    opacity: 0.7,
  },
  primaryButtonLabel: {
    color: '#ffffff',
    fontSize: 18,
    fontWeight: '600',
  },
});
