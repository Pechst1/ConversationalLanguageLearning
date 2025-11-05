import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { AppNavigator } from './AppNavigator';
import { AuthNavigator } from './AuthNavigator';

export interface RootNavigatorProps {
  isAuthenticated: boolean;
  onSignIn: () => void;
  onSignOut: () => void;
}

export const RootNavigator: React.FC<RootNavigatorProps> = ({
  isAuthenticated,
  onSignIn,
  onSignOut
}) => {
  return (
    <NavigationContainer>
      {isAuthenticated ? (
        <AppNavigator onSignOut={onSignOut} />
      ) : (
        <AuthNavigator onSignIn={onSignIn} />
      )}
    </NavigationContainer>
  );
};
