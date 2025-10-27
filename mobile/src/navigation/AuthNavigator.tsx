import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { View, StyleSheet } from 'react-native';
import { Button, Text, spacing } from '../ui';

type AuthStackParamList = {
  SignIn: undefined;
};

const Stack = createNativeStackNavigator<AuthStackParamList>();

const SignInScreen: React.FC<{ onSignIn: () => void }> = ({ onSignIn }) => {
  return (
    <View style={styles.container}>
      <Text variant="headline" emphasis="bold" style={styles.heading}>
        Welcome back
      </Text>
      <Text color="textSecondary" style={styles.copy}>
        Sign in to keep learning new phrases and track your progress.
      </Text>
      <Button label="Sign in" onPress={onSignIn} />
    </View>
  );
};

interface AuthNavigatorProps {
  onSignIn: () => void;
}

export const AuthNavigator: React.FC<AuthNavigatorProps> = ({ onSignIn }) => {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="SignIn">
        {() => <SignInScreen onSignIn={onSignIn} />}
      </Stack.Screen>
    </Stack.Navigator>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    padding: spacing.xl
  },
  heading: {
    marginBottom: spacing.lg
  },
  copy: {
    marginBottom: spacing.xl
  }
});
